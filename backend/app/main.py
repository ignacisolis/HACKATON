"""API del visor SPHEREx (contracts/api.md v0). Ejecutar desde backend/:  uvicorn app.main:app --reload"""
from __future__ import annotations

import logging
import os
import re
import threading
from contextlib import asynccontextmanager

from astropy import units as u
from astropy.coordinates import SkyCoord
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import cache, frames, irsa, precompute, render, science
from .settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

log = logging.getLogger("app")


def warm_targets() -> None:
    """Deja en memoria los objetivos precalculados: primero los cuadros (con el índice en disco,
    menos de 1 s) y después los espectros (~10 s cada uno), para que la demo responda al instante."""
    ready = [t for t in precompute.load_summary() if t.get("cached")]
    for t in ready:
        try:
            frames.list_frames(frames.resolve(None, None, t["size"], t["key"]), do_prefetch=False)
            log.info("objetivo listo en memoria: %s", t["key"])
        except Exception as e:  # el arranque nunca debe caerse por esto
            log.warning("no se pudo precalentar %s: %s", t["key"], e)
    for t in ready:
        try:
            frames.spectrum(frames.resolve(None, None, t["size"], t["key"]))
            log.info("espectro listo en memoria: %s", t["key"])
        except Exception as e:
            log.warning("no se pudo precalentar el espectro de %s: %s", t["key"], e)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.environ.get("SPHEREX_WARM", "1") == "1":
        threading.Thread(target=warm_targets, name="warm-targets", daemon=True).start()
    yield


app = FastAPI(title="SPHEREx Visor API", version="0.2.0", lifespan=lifespan,
              description="Contrato: contracts/api.md (v0). Errores siempre como {error, detail}.")
DIFF_HEADERS = ["X-Dipole-SNR", "X-Dipole-Detected", "X-Diff-Vmax"]
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"],
                   expose_headers=DIFF_HEADERS)  # sin esto el navegador no deja leer los headers de /diff

_ID_RE = re.compile(r"^[0-9A-Za-z_]+$")
_ERROR_NAMES = {400: "bad_request", 404: "not_found", 422: "invalid_parameter",
                501: "not_implemented", 502: "irsa_unavailable"}


# ---------- errores: siempre JSON {error, detail} (contrato, principio 4) ----------

class ApiError(HTTPException):
    """HTTPException con un código de error propio (p. ej. not_comparable)."""

    def __init__(self, status_code: int, error: str, detail: str):
        super().__init__(status_code, detail)
        self.error = error


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    error = getattr(exc, "error", None) or _ERROR_NAMES.get(exc.status_code, "error")
    return JSONResponse({"error": error, "detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    detail = "; ".join(f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors())
    return JSONResponse({"error": "invalid_parameter", "detail": detail}, status_code=422)


# ---------- parámetros comunes ----------

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


def resolve(ra: str | None, dec: str | None, size: float | None, target: str | None) -> frames.Query:
    """`target` (eps_ind_b, wise_0855, rw_aur, r_dra) gana sobre ra/dec."""
    if target is not None and target not in science.target_keys():
        raise HTTPException(422, f"target desconocido: {target!r}. Opciones: {science.target_keys()}")
    if target is None and (ra is None or dec is None):
        raise HTTPException(422, "hace falta target, o bien ra y dec")
    ra_d, dec_d = parse_coords(ra, dec) if target is None else (None, None)
    return frames.resolve(ra_d, dec_d, check_size(size), target)


def parse_detector(detector: str | None) -> int | None:
    if detector is None:
        return None
    m = re.fullmatch(r"[Dd]?([1-6])", detector.strip())
    if not m:
        raise HTTPException(422, "detector debe ser D1..D6")
    return int(m[1])


def obs_or_404(frame_id: str) -> irsa.Observation:
    o = cache.load_observation(frame_id) if _ID_RE.match(frame_id) else None
    if o is None:
        raise HTTPException(404, "cuadro desconocido: primero pide /api/frames para esa posición")
    return o


def cutout_or_502(o: irsa.Observation, q: frames.Query) -> cache.Cutout:
    try:
        return cache.get_cutout(o, q.ra, q.dec, q.size)
    except irsa.IrsaError as e:
        raise HTTPException(502, str(e)) from e


def irsa_guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except irsa.IrsaError as e:
        raise HTTPException(502, str(e)) from e


def core_guard(fn, *args, **kwargs):
    """Las funciones de core/ que aún no existen (tareas 22 y 23) responden 501, no 500."""
    try:
        return irsa_guard(fn, *args, **kwargs)
    except NotImplementedError as e:
        raise HTTPException(501, f"core/ todavía no implementa esto: {e}") from e


# ---------- endpoints ----------

@app.get("/", include_in_schema=False)
def root():
    """La raíz lleva a la documentación interactiva (antes daba 404)."""
    return RedirectResponse("/docs")


@app.get("/api/health")
def health():
    s = get_settings()
    return {"status": "ok", "collections": list(s.collections), "label": s.release_label}


@app.get("/api/targets")
def get_targets():
    """Objetivos de la demo con las coordenadas EXACTAS que están precalculadas en caché."""
    return {"targets": precompute.load_summary()}


@app.get("/api/frames")
def get_frames(
    ra: str | None = None, dec: str | None = None, target: str | None = None,
    size: float | None = None,
    band: int | None = Query(None, ge=1, le=102),
    detector: str | None = None,
    prefetch: bool = True,
    limit: int | None = Query(None, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    q = resolve(ra, dec, size, target)
    return irsa_guard(frames.list_frames, q, band, parse_detector(detector), prefetch, limit, offset)


@app.get("/api/coverage")
def get_coverage(ra: str | None = None, dec: str | None = None, target: str | None = None,
                 size: float | None = None):
    return irsa_guard(frames.coverage, resolve(ra, dec, size, target))


@app.get("/api/frame/{frame_id}/png")
def get_frame_png(
    frame_id: str, ra: str | None = None, dec: str | None = None, target: str | None = None,
    size: float | None = None,
    layer: str = Query("image", pattern="^(image|image-zodi|variance|flags)$"),
    bits: str | None = Query(None, description="bits o nombres de FLAGS separados por coma (layer=flags)"),
    stretch: str = Query("asinh", pattern="^(linear|asinh)$"),
    vmin: float | None = None, vmax: float | None = None,
):
    q = resolve(ra, dec, size, target)
    c = cutout_or_502(obs_or_404(frame_id), q)
    try:
        bit_list = [science.bit_of(b.strip()) for b in bits.split(",") if b.strip()] if bits else None
    except KeyError as e:
        raise HTTPException(422, str(e)) from e
    png = render.render_png(c, q.ra, q.dec, q.size, layer, bit_list, vmin, vmax, stretch)
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/frame/{frame_id}/image.png", include_in_schema=False)
def get_frame_image_legacy(frame_id: str, ra: str | None = None, dec: str | None = None,
                           target: str | None = None, size: float | None = None,
                           layer: str = "image", bits: str | None = None,
                           vmin: float | None = None, vmax: float | None = None):
    """Ruta vieja (PR #1); la del contrato es /png."""
    return get_frame_png(frame_id, ra, dec, target, size, layer, bits, "linear", vmin, vmax)


@app.get("/api/frame/{frame_id}/meta")
def get_frame_meta(frame_id: str, ra: str | None = None, dec: str | None = None,
                   target: str | None = None, size: float | None = None):
    q = resolve(ra, dec, size, target)
    o = obs_or_404(frame_id)
    return frames.frame_meta(o, cutout_or_502(o, q), q)


@app.get("/api/spectrum")
def get_spectrum(ra: str | None = None, dec: str | None = None, target: str | None = None,
                 size: float | None = None):
    try:
        return core_guard(frames.spectrum, resolve(ra, dec, size, target))
    except frames.TooHeavy as e:
        raise ApiError(503, "too_heavy", str(e)) from e


@app.get("/api/lightcurve")
def get_lightcurve(band: int = Query(..., ge=1, le=102), ra: str | None = None,
                   dec: str | None = None, target: str | None = None, size: float | None = None):
    return core_guard(frames.lightcurve, resolve(ra, dec, size, target), band)


@app.get("/api/diff")
def get_diff(
    a: str, b: str, ra: str | None = None, dec: str | None = None, target: str | None = None,
    size: float | None = None, vmax: float | None = Query(None, gt=0),
    format: str = Query("png", pattern="^(png|json)$"),
    zodi: bool = Query(True, description="restar el modelo de luz zodiacal antes de la resta"),
):
    """a − b en MJy/sr (core.subtract_frames) en la misma grilla que /png.

    PNG con escala divergente simétrica [−vmax, +vmax] (gris medio = 0). Un objeto que se movió
    deja un dipolo: blanco donde está en `a`, negro donde estaba en `b`. Headers: X-Dipole-SNR
    (el menor de los dos lóbulos, en sigmas), X-Dipole-Detected y X-Diff-Vmax.
    `format=json` devuelve solo la medición, sin imagen.
    """
    q = resolve(ra, dec, size, target)
    oa, ob = obs_or_404(a), obs_or_404(b)
    try:
        res = irsa_guard(frames.diff, q, oa, ob, zodi)
    except frames.NotComparable as e:
        raise ApiError(422, "not_comparable", str(e)) from e
    info = res["info"]
    if format == "json":
        return info
    dip = info["dipole"]
    snr = min(dip.get("pos_snr") or 0.0, dip.get("neg_snr") or 0.0)
    v = vmax or res["vmax_auto"]
    headers = {"X-Dipole-SNR": f"{snr:.2f}", "X-Dipole-Detected": str(bool(dip.get("detected"))).lower(),
               "X-Diff-Vmax": f"{v:.6g}", "Cache-Control": "public, max-age=86400"}
    return Response(render.diff_png(res["diff"], v), media_type="image/png", headers=headers)


@app.get("/api/pairs")
def get_pairs(ra: str | None = None, dec: str | None = None, target: str | None = None,
              size: float | None = None, band: int | None = Query(None, ge=1, le=102),
              detector: str | None = None, limit: int = Query(50, ge=1, le=1000)):
    """Pares de cuadros restables (core.is_comparable), del más separado en el tiempo al menos."""
    q = resolve(ra, dec, size, target)
    return irsa_guard(frames.pairs, q, parse_detector(detector), band, limit)
