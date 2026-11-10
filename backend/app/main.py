"""API del visor SPHEREx. Ejecutar desde backend/:  uvicorn app.main:app --reload"""
from __future__ import annotations

import logging
import re

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from . import cache, frames, irsa, precompute, render
from .settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="SPHEREx Visor API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

_ID_RE = re.compile(r"^[0-9A-Za-z_]+$")


def parse_coords(ra: str, dec: str) -> tuple[float, float]:
    """Acepta grados (133.795, -7.245) o sexagesimal (08h55m10.831s / 08:55:10.8, -7d14m42.53s)."""
    try:
        sexa = bool(re.search(r"[hms:\s]", ra.strip()))
        c = SkyCoord(ra, dec, unit=(u.hourangle if sexa else u.deg, u.deg), frame="icrs")
    except Exception as e:
        raise HTTPException(422, f"coordenadas inválidas: {e}") from e
    # 1e-5° ≈ 0.04″: misma posición -> misma clave de caché, venga en grados o sexagesimal
    return round(float(c.ra.deg), 5), round(float(c.dec.deg), 5)


def check_size(size: float | None) -> float:
    s = get_settings()
    size = s.default_size_deg if size is None else size
    if not 0 < size <= s.max_size_deg:
        raise HTTPException(422, f"size debe estar entre 0 y {s.max_size_deg} grados")
    return size


def obs_or_404(frame_id: str) -> irsa.Observation:
    o = cache.load_observation(frame_id) if _ID_RE.match(frame_id) else None
    if o is None:
        raise HTTPException(404, "cuadro desconocido: primero pide /api/frames para esa posición")
    return o


def cutout_or_502(o: irsa.Observation, ra: float, dec: float, size: float) -> cache.Cutout:
    try:
        return cache.get_cutout(o, ra, dec, size)
    except irsa.IrsaError as e:
        raise HTTPException(502, str(e)) from e


@app.get("/api/health")
def health():
    s = get_settings()
    return {"status": "ok", "collections": list(s.collections), "label": s.release_label}


@app.get("/api/frames")
def get_frames(
    ra: str, dec: str,
    size: float | None = None,
    band: int | None = Query(None, ge=1, le=102),
    detector: int | None = Query(None, ge=1, le=6),
    prefetch: bool = True,
):
    ra_d, dec_d = parse_coords(ra, dec)
    try:
        return frames.list_frames(ra_d, dec_d, check_size(size), band, detector, prefetch)
    except irsa.IrsaError as e:
        raise HTTPException(502, str(e)) from e


@app.get("/api/targets")
def get_targets():
    """Objetivos de la demo con las coordenadas EXACTAS que están precalculadas en caché."""
    return {"targets": precompute.load_summary()}


@app.get("/api/coverage")
def get_coverage(ra: str, dec: str, size: float | None = None):
    ra_d, dec_d = parse_coords(ra, dec)
    try:
        return frames.coverage(ra_d, dec_d, check_size(size))
    except irsa.IrsaError as e:
        raise HTTPException(502, str(e)) from e


@app.get("/api/frame/{frame_id}/image.png")
def get_frame_image(
    frame_id: str, ra: str, dec: str, size: float | None = None,
    layer: str = Query("image", pattern="^(image|image-zodi|variance|flags)$"),
    bits: str | None = Query(None, description="bits de FLAGS separados por coma (layer=flags)"),
    vmin: float | None = None, vmax: float | None = None,
):
    ra_d, dec_d = parse_coords(ra, dec)
    size = check_size(size)
    c = cutout_or_502(obs_or_404(frame_id), ra_d, dec_d, size)
    bit_list = [int(b) for b in bits.split(",") if b.strip()] if bits else None
    png = render.render_png(c, ra_d, dec_d, size, layer, bit_list, vmin, vmax)
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/frame/{frame_id}/meta")
def get_frame_meta(frame_id: str, ra: str, dec: str, size: float | None = None):
    ra_d, dec_d = parse_coords(ra, dec)
    size = check_size(size)
    o = obs_or_404(frame_id)
    c = cutout_or_502(o, ra_d, dec_d, size)
    h = c.header
    lam = c.wavelength_at(ra_d, dec_d)
    x, y = c.wcs.all_world2pix([[ra_d, dec_d]], 0)[0]
    i, j = int(round(float(y))), int(round(float(x)))
    inside = 0 <= i < c.flags.shape[0] and 0 <= j < c.flags.shape[1]
    target_flags = int(c.flags[i, j]) if inside else None
    n_pix = c.flags.size
    s = get_settings()
    return {
        "id": o.id,
        "observation": o.to_dict(),
        "date_obs": h.get("DATE-OBS"),
        "mjd_avg": h.get("MJD-AVG"),
        "exposure_s": h.get("XPOSURE"),
        "detector": o.detector,
        "wavelength_um": lam,
        "band": s.band_of(o.detector, lam) if lam is not None else None,
        "bandwidth_um": float(c.bandwidth_um[i, j]) if inside else None,
        "bunit": h.get("BUNIT"),
        "psf_fwhm_arcsec": h.get("PSF_FWHM"),
        "quality": {"l1": h.get("L1DQAFLG"), "l2": h.get("L2DQAFLG"), "fine_astrometry": h.get("FINAST")},
        "shape": list(c.image.shape),
        "target_pixel": {"x": float(x), "y": float(y), "inside": inside,
                         "value": float(c.image[i, j]) if inside else None,
                         "variance": float(c.variance[i, j]) if inside else None,
                         "zodi": float(c.zodi[i, j]) if inside else None},
        "flags": [
            {"bit": bit, "name": name,
             "fraction": round(float(np.mean((c.flags & (1 << bit)) > 0)), 4),
             "at_target": bool(target_flags & (1 << bit)) if target_flags is not None else None}
            for name, bit in sorted(c.flag_bits.items(), key=lambda kv: kv[1])
        ],
        "flags_pixels": n_pix,
    }
