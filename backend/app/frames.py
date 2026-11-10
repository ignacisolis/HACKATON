"""Lógica de /api/frames: lista de cuadros + descarga progresiva en segundo plano."""
from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from astropy.time import Time

from . import cache, irsa
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


def list_frames(ra: float, dec: float, size_deg: float, band: int | None = None,
                detector: int | None = None, do_prefetch: bool = True,
                s: Settings | None = None) -> dict:
    s = s or get_settings()
    obs = observations_at(ra, dec, s)

    lam_range = None
    if band is not None:
        det_b, lo, hi = s.band_range_um(band)
        if detector is not None and detector != det_b:
            obs = []
        detector, lam_range = det_b, (lo, hi)
    if detector is not None:
        obs = [o for o in obs if o.detector == detector]

    frames, missing = [], []
    for o in obs:
        c = cache.get_cached(o.id, ra, dec, size_deg, s)
        lam = c.wavelength_at(ra, dec) if c else None
        if c is None:
            missing.append(o)
        elif lam_range and (lam is None or not lam_range[0] <= lam < lam_range[1]):
            continue  # ya sabemos su λ y no cae en la banda pedida
        q = f"ra={ra:.5f}&dec={dec:.5f}&size={size_deg:g}"
        frames.append({
            "id": o.id,
            "date": Time(o.mjd_start, format="mjd").isot[:19] + "Z",
            "mjd": o.mjd_start,
            "detector": o.detector,
            "wavelength_um": round(lam, 4) if lam is not None else None,
            "band": s.band_of(o.detector, lam) if lam is not None else None,
            "version": o.version,
            "ready": c is not None,
            "image_url": f"/api/frame/{o.id}/image.png?{q}",
            "meta_url": f"/api/frame/{o.id}/meta?{q}",
        })

    queued = prefetch(missing, ra, dec, size_deg, s) if do_prefetch and missing else 0
    return {
        "query": {"ra": ra, "dec": dec, "size": size_deg, "band": band, "detector": detector},
        "release": {"name": s.release_name, "label": s.release_label},
        "count": len(frames),
        "pending": len(missing),
        "queued": queued,
        "complete": not missing,
        "frames": frames,
    }
