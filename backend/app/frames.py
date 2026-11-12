"""Lógica de /api/frames: lista de cuadros + descarga progresiva en segundo plano."""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import numpy as np
from astropy.time import Time

from . import cache, irsa, render, science
from .settings import Settings, get_settings

log = logging.getLogger(__name__)

_pool: ThreadPoolExecutor | None = None
_inflight: set[str] = set()
_inflight_guard = threading.Lock()


def _executor(s: Settings) -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(max_workers=s.max_workers, thread_name_prefix="irsa")
    return _pool


def observations_at(ra: float, dec: float, s: Settings | None = None) -> list[irsa.Observation]:
    """Observaciones que cubren (ra, dec). La 2ª consulta igual sale del disco, sin tocar IRSA."""
    s = s or get_settings()
    qpath = s.cache_dir / "queries" / f"{ra:.5f}_{dec:+.5f}.json"
    if qpath.exists():
        ids = json.loads(qpath.read_text())
        found = [cache.load_observation(i, s) for i in ids]
        if all(found):
            return found  # type: ignore[return-value]
    obs = irsa.query_observations(ra, dec, s)
    cache.save_observations(obs, s)
    qpath.parent.mkdir(parents=True, exist_ok=True)
    qpath.write_text(json.dumps([o.id for o in obs]))
    return obs


def prefetch(obs: list[irsa.Observation], ra: float, dec: float, size_deg: float,
             s: Settings | None = None) -> int:
    """Encola la descarga de los cutouts que faltan. Devuelve cuántos quedaron encolados."""
    s = s or get_settings()
    queued = 0
    for o in obs:
        key = cache.cutout_key(o.id, ra, dec, size_deg)
        with _inflight_guard:
            if key in _inflight:
                continue
            _inflight.add(key)
        queued += 1

        def job(o=o, key=key):
            try:
                cache.get_cutout(o, ra, dec, size_deg, s)
            except Exception as e:  # una descarga fallida no tumba al resto
                log.warning("cutout %s falló: %s", key, e)
            finally:
                with _inflight_guard:
                    _inflight.discard(key)

        _executor(s).submit(job)
    return queued


# ---------- consulta: posición o objetivo ----------

@dataclass(frozen=True)
class Query:
    """Lo que pidió el usuario, ya resuelto (contracts/api.md · Parámetros comunes)."""
    ra: float            # centro del recorte (clave de caché)
    dec: float
    size: float
    target: str | None = None

    def to_dict(self) -> dict:
        d = {"ra": self.ra, "dec": self.dec, "size": self.size, "target": self.target}
        if self.target:
            d["resolved_from"] = "targets.yaml + movimiento propio"
            d["coord_epoch_applied"] = science.window_center(self.target)[2]
        return d

    @property
    def qs(self) -> str:
        q = f"ra={self.ra}&dec={self.dec}&size={self.size:g}"
        return q + (f"&target={self.target}" if self.target else "")


def resolve(ra: float | None, dec: float | None, size: float, target: str | None) -> Query:
    """`target` gana sobre ra/dec: el recorte se centra donde está el objetivo en 2025-26."""
    if target:
        t_ra, t_dec, _ = science.window_center(target)
        return Query(t_ra, t_dec, size, target)
    if ra is None or dec is None:
        raise ValueError("hace falta target, o bien ra y dec")
    return Query(ra, dec, size, None)


# ---------- resumen por cuadro: memoria + índice en disco ----------
# El resumen (λ y ancho en el objetivo, banda, target_xy, flagged_fraction, quality,
# display_range) se calcula una vez por cuadro y consulta, y se guarda en
# cache/index/<consulta>.json. Así el servidor arranca sin abrir miles de .npz y los
# pares restables (/api/pairs) salen del índice sin bajar ni leer nada.

SUMMARY_VERSION = 2  # subir si cambia lo que guarda summarize(): invalida los índices viejos

_summary_memo: dict[str, dict] = {}
_index_loaded: set[str] = set()
_index_dirty: set[str] = set()
_query_locks: dict[Query, threading.Lock] = {}


def _query_lock(q: Query) -> threading.Lock:
    with _inflight_guard:
        return _query_locks.setdefault(q, threading.Lock())


def _qkey(q: Query) -> str:
    return f"{q.ra:.5f}_{q.dec:+.5f}_{q.size:.4f}_{q.target or 'radec'}"


def _index_path(q: Query, s: Settings):
    return s.cache_dir / "index" / f"{_qkey(q)}.json"


def _memo_key(o_id: str, q: Query, s: Settings) -> str:
    return f"{s.cache_dir}/{_qkey(q)}/{o_id}"


def _load_index(q: Query, s: Settings) -> None:
    k = f"{s.cache_dir}/{_qkey(q)}"
    if k in _index_loaded:
        return
    _index_loaded.add(k)
    p = _index_path(q, s)
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text())
    except ValueError:
        return  # índice corrupto: se reconstruye solo
    if data.get("version") != SUMMARY_VERSION:
        return
    for o_id, sm in data["frames"].items():
        _summary_memo.setdefault(_memo_key(o_id, q, s), sm)


def save_index(q: Query, s: Settings) -> None:
    """Escribe el índice de la consulta si hubo resúmenes nuevos (escritura atómica)."""
    k = f"{s.cache_dir}/{_qkey(q)}"
    if k not in _index_dirty:
        return
    prefix = k + "/"
    frames_ = {mk[len(prefix):]: sm for mk, sm in list(_summary_memo.items()) if mk.startswith(prefix)}
    p = _index_path(q, s)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": SUMMARY_VERSION, "query": q.to_dict(), "frames": frames_}))
    tmp.replace(p)
    _index_dirty.discard(k)


def frame_summary(o: irsa.Observation, q: Query, s: Settings) -> dict | None:
    """Resumen de un cuadro cacheado: memoria, después índice en disco, y si no, el .npz."""
    _load_index(q, s)
    key = _memo_key(o.id, q, s)
    if key in _summary_memo:
        return _summary_memo[key]
    c = cache.get_cached(o.id, q.ra, q.dec, q.size, s)
    if c is None:
        return None
    _summary_memo[key] = summary = summarize(c, o, q, s)
    _index_dirty.add(f"{s.cache_dir}/{_qkey(q)}")
    return summary


def summarize(c: cache.Cutout, o: irsa.Observation, q: Query, s: Settings) -> dict:
    mjd = science.frame_mjd(c, o)
    t_ra, t_dec = science.position_at(q.target, q.ra, q.dec, mjd)
    x, y = c.wcs.all_world2pix([[t_ra, t_dec]], 0)[0]
    i, j = int(round(float(y))), int(round(float(x)))
    inside = 0 <= i < c.image.shape[0] and 0 <= j < c.image.shape[1]
    lam = float(c.wave_um[i, j]) if inside and np.isfinite(c.wave_um[i, j]) else None
    bw = float(c.bandwidth_um[i, j]) if inside and np.isfinite(c.bandwidth_um[i, j]) else None
    frac = science.flagged_fraction(c.flags)
    masked = bool(inside and science.core_flags.mask_for(c.flags[i:i + 1, j:j + 1], science.PHOTOMETRY)[0, 0])
    return {
        "mjd": mjd,
        "wavelength_um": round(lam, 4) if lam is not None else None,
        "bandwidth_um": round(bw, 4) if bw is not None else None,
        "band": science.band_of(o.detector, lam) if lam is not None else None,
        "target_radec": [round(t_ra, 6), round(t_dec, 6)],
        "target_pixel": {"x": float(x), "y": float(y), "inside": inside},
        "target_xy": render.grid_xy(q.ra, q.dec, q.size, t_ra, t_dec),
        "flagged_fraction": frac,
        "quality": science.quality(c, inside, masked, frac),
        "display_range": render.display_range(render.reproject(c, c.image, q.ra, q.dec, q.size)),
    }


def frame_item(o: irsa.Observation, q: Query, sm: dict | None, s: Settings) -> dict:
    mjd = sm["mjd"] if sm else (o.mjd_start + o.mjd_end) / 2
    base = f"/api/frame/{o.id}"
    return {
        "id": o.id,
        "mjd": mjd,
        "date": Time(mjd, format="mjd").isot,
        "detector": f"D{o.detector}",
        "wavelength_um": sm and sm["wavelength_um"],
        "bandwidth_um": sm and sm["bandwidth_um"],
        "band": sm and sm["band"],
        "release": o.version,
        "collection": o.collection,
        "image_url": f"{base}/png?{q.qs}&stretch=asinh",
        "meta_url": f"{base}/meta?{q.qs}",
        "target_xy": sm and sm["target_xy"],
        "flagged_fraction": sm and sm["flagged_fraction"],
        "quality": sm and sm["quality"],
        "display_range": sm and sm["display_range"],
        "ready": sm is not None,
    }


# ---------- GET /api/frames ----------

def list_frames(q: Query, band: int | None = None, detector: int | None = None,
                do_prefetch: bool = True, limit: int | None = None, offset: int = 0,
                s: Settings | None = None) -> dict:
    s = s or get_settings()
    obs = observations_at(q.ra, q.dec, s)

    lam_range = None
    if band is not None:
        det_b, lo, hi = science.band_range(band)
        if detector is not None and detector != det_b:
            obs = []
        detector, lam_range = det_b, (lo, hi)
    if detector is not None:
        obs = [o for o in obs if o.detector == detector]

    items, missing = [], []
    with _query_lock(q):  # si el precalentamiento ya está en esta consulta, se espera en vez de duplicar
        summaries = [frame_summary(o, q, s) for o in obs]
        save_index(q, s)
    for o, sm in zip(obs, summaries):
        if sm is None:
            missing.append(o)
        elif lam_range and (sm["wavelength_um"] is None
                            or not lam_range[0] <= sm["wavelength_um"] < lam_range[1]):
            continue  # ya sabemos su λ y no cae en la banda pedida
        items.append(frame_item(o, q, sm, s))

    items.sort(key=lambda f: f["mjd"])
    queued = prefetch(missing, q.ra, q.dec, q.size, s) if do_prefetch and missing else 0
    page = items[offset:offset + limit] if limit else items[offset:]
    return {
        "query": {**q.to_dict(), "band": band, "detector": f"D{detector}" if detector else None},
        "release": {"collections": list(s.collections), "label": s.release_label},
        "n_frames": len(items),
        "n_dates": len({f["date"][:10] for f in items}),
        "pending": len(missing),
        "queued": queued,
        "complete": not missing,
        "offset": offset,
        "limit": limit,
        "frames": page,
    }


# ---------- GET /api/frame/{id}/meta ----------

def _finite(v) -> float | None:
    """JSON no admite NaN: un píxel sin dato (p. ej. el núcleo saturado de R Dra) viaja como null."""
    v = float(v)
    return v if np.isfinite(v) else None


def frame_meta(o: irsa.Observation, c: cache.Cutout, q: Query, s: Settings | None = None) -> dict:
    s = s or get_settings()
    sm = summarize(c, o, q, s)
    h = c.header
    w = c.wcs.wcs
    tp = sm["target_pixel"]
    i, j = int(round(tp["y"])), int(round(tp["x"]))
    at = (lambda arr: _finite(arr[i, j])) if tp["inside"] else (lambda arr: None)
    flags_block = science.flags_report(c)
    target_bits = int(c.flags[i, j]) if tp["inside"] else 0
    flags_block["at_target"] = [science.core_flags.name_of(b) for b in range(32)
                                if target_bits & (1 << b) and b in science.core_flags.known_bits()]
    return {
        "id": o.id,
        "mjd": sm["mjd"],
        "date": Time(sm["mjd"], format="mjd").isot,
        "detector": f"D{o.detector}",
        "release": o.version,
        "collection": o.collection,
        "exposure_s": h.get("XPOSURE"),
        "wavelength_um": sm["wavelength_um"],
        "bandwidth_um": sm["bandwidth_um"],
        "band": sm["band"],
        "wcs": {"crval": [float(v) for v in w.crval], "ctype": list(w.ctype)},
        "flags": flags_block,
        "mask_layers": science.mask_layers(c),
        "flagged_fraction": sm["flagged_fraction"],
        "quality": sm["quality"],
        "target": {
            "key": q.target, "radec": sm["target_radec"], "xy": sm["target_xy"],
            "inside": tp["inside"], "value": at(c.image), "variance": at(c.variance), "zodi": at(c.zodi),
        },
        "psf_fwhm_arcsec": h.get("PSF_FWHM"),
        "dqa": {"l1": h.get("L1DQAFLG"), "l2": h.get("L2DQAFLG")},
        "bunit": h.get("BUNIT"),
        "shape": list(c.image.shape),
    }


# ---------- GET /api/spectrum y /api/lightcurve ----------

def ready_frames(q: Query, s: Settings) -> list:
    """core.Frame de todas las exposiciones ya cacheadas en esa posición."""
    out = []
    for o in observations_at(q.ra, q.dec, s):
        c = cache.get_cached(o.id, q.ra, q.dec, q.size, s)
        if c is not None:
            out.append(science.to_frame(c, o, q.target, q.ra, q.dec))
    return out


def _point(p) -> dict:
    """SpectrumPoint de core.combine -> punto del contrato (band, n_epochs y unit vienen de core)."""
    return {
        "wavelength_um": p.wavelength_um, "bandwidth_um": p.bandwidth_um, "band": p.band,
        "flux": p.flux, "flux_err": p.flux_err, "unit": p.unit, "detector": p.detector,
        "n_epochs": p.n_epochs, "flagged_fraction": p.flagged_fraction, "quality": p.quality,
    }


_spectrum_memo: dict[tuple, dict] = {}


class TooHeavy(RuntimeError):
    """El cálculo pide más memoria de la que este servidor permite (SPHEREX_SPECTRUM_MAX_FRAMES)."""


def _spectrum_path(q: Query, n_ready: int, s: Settings):
    return s.cache_dir / "spectra" / f"{_qkey(q)}_{n_ready}.json"


def spectrum(q: Query, s: Settings | None = None) -> dict:
    """Espectro memorizado en RAM y en disco (cache/spectra/), por consulta y nº de cuadros en caché.

    Calcularlo carga en memoria TODAS las exposiciones cacheadas (R Dra: 2476, ~360 MB). En un
    servidor chico se precalcula en local (app.precompute) y viaja con la caché; si falta y hay
    más cuadros que SPHEREX_SPECTRUM_MAX_FRAMES, se responde 503 en vez de quedarse sin memoria.
    """
    s = s or get_settings()
    n_ready = sum(1 for o in observations_at(q.ra, q.dec, s)
                  if cache.get_cached_path(o.id, q.ra, q.dec, q.size, s).exists())
    key = (str(s.cache_dir), q, n_ready)
    if key in _spectrum_memo:
        return _spectrum_memo[key]
    path = _spectrum_path(q, n_ready, s)
    if path.exists():
        _spectrum_memo[key] = json.loads(path.read_text())
        return _spectrum_memo[key]
    limit = int(os.environ.get("SPHEREX_SPECTRUM_MAX_FRAMES", "0") or 0)
    if limit and n_ready > limit:
        raise TooHeavy(f"el espectro de este punto usa {n_ready} exposiciones y este servidor admite "
                       f"hasta {limit}; los 4 objetivos de la demo vienen precalculados")
    _spectrum_memo[key] = result = _spectrum(q, s)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result))
    tmp.replace(path)
    return result


def _spectrum(q: Query, s: Settings) -> dict:
    frames = ready_frames(q, s)
    points = science.extract_spectrum(frames, q.target, q.ra, q.dec)
    combined = science.combine(points)
    return {
        "query": q.to_dict(),
        "aperture_px": science.DEFAULT_APERTURE_PX,
        "mask_purpose": science.PHOTOMETRY,
        "n_points": len(combined),
        "n_epochs_used": len(points),
        "n_frames_cached": len(frames),
        "points": [_point(p) for p in combined],
        # Un punto por exposición, sin combinar: de acá sale /api/lightcurve sin volver a
        # abrir los cuadros (en Render, recalcularlo tardaba ~1 min).
        "exposures": [_jsonable(dataclasses.asdict(p)) for p in points],
    }


def _exposure_points(q: Query, s: Settings) -> list:
    """Los SpectrumPoint por exposición guardados con el espectro (lo calcula si hace falta)."""
    from core.datatypes import SpectrumPoint

    sp = spectrum(q, s)
    if "exposures" not in sp:  # espectro guardado por una versión anterior
        return science.extract_spectrum(ready_frames(q, s), q.target, q.ra, q.dec)
    # JSON guarda NaN como null: los campos float vuelven a NaN (p. ej. λ de un píxel saturado de R Dra)
    floats = {f.name for f in dataclasses.fields(SpectrumPoint) if "float" in str(f.type)}
    return [SpectrumPoint(**{k: float("nan") if v is None and k in floats else v for k, v in e.items()})
            for e in sp["exposures"]]


def lightcurve(q: Query, band: int, s: Settings | None = None) -> dict:
    s = s or get_settings()
    det, lo, hi = science.band_range(band)
    points = _exposure_points(q, s)
    mjds, flux, err = science.light_curve(points, band)
    return {"query": {**q.to_dict(), "band": band}, "band_range_um": [lo, hi],
            "mjds": [float(m) for m in mjds], "flux": [float(f) for f in flux],
            "flux_err": [float(e) for e in err]}


# ---------- GET /api/coverage ----------

def coverage(q: Query, s: Settings | None = None) -> dict:
    """Qué hay en el punto sin bajar cutouts: por detector, colección, fecha, época y banda.

    La banda (1..102) necesita el λ del píxel, que solo se conoce con el cutout:
    `bands` cuenta solo lo cacheado y `bands_known` dice cuántas exposiciones son.
    """
    s = s or get_settings()
    obs = observations_at(q.ra, q.dec, s)
    by_det: dict[str, int] = {}
    by_date: dict[str, dict] = {}
    by_coll: dict[str, int] = {}
    bands: dict[int, int] = {}
    known = 0
    for o in obs:
        det = f"D{o.detector}"
        by_det[det] = by_det.get(det, 0) + 1
        by_coll[o.collection] = by_coll.get(o.collection, 0) + 1
        day = Time(o.mjd_start, format="mjd").isot[:10]
        d = by_date.setdefault(day, {"date": day, "count": 0, "detectors": set()})
        d["count"] += 1
        d["detectors"].add(det)
        sm = frame_summary(o, q, s)
        if sm and sm["band"] is not None:
            known += 1
            bands[sm["band"]] = bands.get(sm["band"], 0) + 1

    # Épocas: SPHEREx vuelve a la misma zona cada ~6 meses; se cortan huecos de >30 días.
    epochs: list[dict] = []
    for day in sorted(by_date):
        mjd = Time(day).mjd
        if not epochs or mjd - epochs[-1]["_last"] > 30:
            epochs.append({"start": day, "end": day, "count": 0, "_last": mjd})
        e = epochs[-1]
        e["end"], e["_last"] = day, mjd
        e["count"] += by_date[day]["count"]
    for e in epochs:
        del e["_last"]
    save_index(q, s)

    return {
        "query": q.to_dict(),
        "release": {"collections": list(s.collections), "label": s.release_label},
        "total": len(obs),
        "detectors": dict(sorted(by_det.items())),
        "collections": by_coll,
        "dates": [{**v, "detectors": sorted(v["detectors"])} for _, v in sorted(by_date.items())],
        "epochs": epochs,
        "bands": {str(k): bands[k] for k in sorted(bands)},
        "bands_known": known,
    }


# ---------- GET /api/diff y /api/pairs: resta de cuadros comparables (C5, O4) ----------

class NotComparable(ValueError):
    """Los cuadros no se pueden restar; el mensaje es el motivo de core.is_comparable."""


def _grid_frame(o: irsa.Observation, q: Query, s: Settings, subtract_zodi: bool = True):
    """Cuadro llevado a la grilla de cielo común, como core.Frame. Las estrellas quedan alineadas."""
    c = cache.get_cutout(o, q.ra, q.dec, q.size, s)
    sm = frame_summary(o, q, s) or summarize(c, o, q, s)
    img, var, flags, w = render.grid_layers(c, q.ra, q.dec, q.size, subtract_zodi)
    f = science.Frame(
        image=img, flags=flags, variance=var, wcs=w, mjd=sm["mjd"], detector=f"D{o.detector}",
        wavelength_um=sm["wavelength_um"] if sm["wavelength_um"] is not None else np.nan,
        bandwidth_um=sm["bandwidth_um"] if sm["bandwidth_um"] is not None else np.nan,
        release=o.version, meta={"id": o.id},
    )
    return f, sm


def _jsonable(v):
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return float(v) if np.isfinite(v) else None
    return v


def diff(q: Query, a: irsa.Observation, b: irsa.Observation, subtract_zodi: bool = True,
         s: Settings | None = None) -> dict:
    """a − b en MJy/sr con core.subtract_frames, y el dipolo de movimiento con core.dipole_snr.

    Por defecto se resta antes el modelo ZODI de cada cuadro: la luz zodiacal cambia entre
    visitas separadas meses y, sin restarla, toda la diferencia queda corrida de cero.
    """
    s = s or get_settings()
    fa, sa = _grid_frame(a, q, s, subtract_zodi)
    fb, sb = _grid_frame(b, q, s, subtract_zodi)
    if sa["wavelength_um"] is None or sb["wavelength_um"] is None:
        raise NotComparable("el objetivo cae fuera del recorte en uno de los cuadros: no hay λ que comparar")
    ok, why = science.core.is_comparable(fa, fb)
    if not ok:
        raise NotComparable(why)
    d, var, usable = science.core.subtract_frames(fa, fb)
    # El dipolo se busca donde está el objetivo a mitad de camino entre las dos fechas.
    t_ra, t_dec = science.position_at(q.target, q.ra, q.dec, (fa.mjd + fb.mjd) / 2)
    center = render.grid_array_xy(q.ra, q.dec, q.size, t_ra, t_dec)
    dipole = science.core.dipole_snr(d, var, center=center)
    finite = np.isfinite(d)
    vmax = float(np.percentile(np.abs(d[finite]), 99.5)) if finite.any() else 1.0
    return {
        "diff": d, "usable": usable, "vmax_auto": vmax,
        "info": _jsonable({
            "query": q.to_dict(),
            "a": {"id": a.id, "mjd": fa.mjd, "detector": fa.detector, "wavelength_um": fa.wavelength_um},
            "b": {"id": b.id, "mjd": fb.mjd, "detector": fb.detector, "wavelength_um": fb.wavelength_um},
            "dt_days": fa.mjd - fb.mjd,
            "unit": "MJy/sr",
            "zodi_subtracted": subtract_zodi,
            "median_diff": float(np.median(d[finite])) if finite.any() else None,
            "vmax_auto": vmax,
            "n_usable": int(usable.sum()),
            "dipole": dipole,
            "dipole_center_xy": render.grid_xy(q.ra, q.dec, q.size, t_ra, t_dec),
        }),
    }


def pairs(q: Query, detector: int | None = None, band: int | None = None, limit: int = 50,
          s: Settings | None = None) -> dict:
    """Pares restables según core.is_comparable, sacados del índice (no abre ni baja nada).

    Ordenados de mayor a menor separación en el tiempo: es donde más se nota el movimiento.
    Solo cuentan los cuadros ya en caché (`ready`); `pending` dice cuántos faltan.
    """
    from types import SimpleNamespace

    s = s or get_settings()
    obs = observations_at(q.ra, q.dec, s)
    if band is not None:
        detector = science.band_range(band)[0]
    if detector is not None:
        obs = [o for o in obs if o.detector == detector]
    _, n = render.target_wcs(q.ra, q.dec, q.size)
    ready, pending = [], 0
    for o in obs:
        sm = frame_summary(o, q, s)
        if sm is None:
            pending += 1
        elif sm["wavelength_um"] is not None and (band is None or sm["band"] == band):
            ready.append((o, sm, SimpleNamespace(
                detector=f"D{o.detector}", wavelength_um=sm["wavelength_um"],
                bandwidth_um=sm["bandwidth_um"], shape=(n, n))))
    save_index(q, s)
    found = []
    for i in range(len(ready)):
        for j in range(i + 1, len(ready)):
            (oa, sa, fa), (ob, sb, fb) = ready[i], ready[j]
            if fa.detector != fb.detector or not science.core.is_comparable(fa, fb)[0]:
                continue
            if sa["mjd"] < sb["mjd"]:  # a = la más reciente: a − b deja + donde está ahora
                (oa, sa), (ob, sb) = (ob, sb), (oa, sa)
            found.append({
                "a": oa.id, "b": ob.id, "detector": fa.detector,
                "dt_days": round(sa["mjd"] - sb["mjd"], 3),
                "wavelength_um": [sa["wavelength_um"], sb["wavelength_um"]],
                "band": [sa["band"], sb["band"]],
                "quality": [sa["quality"], sb["quality"]],
                "diff_url": f"/api/diff?a={oa.id}&b={ob.id}&{q.qs}",
            })
    found.sort(key=lambda p: -p["dt_days"])
    return {"query": {**q.to_dict(), "band": band, "detector": f"D{detector}" if detector else None},
            "n_pairs": len(found), "n_frames_ready": len(ready), "pending": pending,
            "pairs": found[:limit]}
