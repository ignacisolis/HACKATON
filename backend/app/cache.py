"""Caché compacta de cutouts: se guarda todo menos la PSF (~100 KB en vez de ~5 MB).

Estructura en disco (config/release.yaml -> cache.dir):
    obs/<obs_id>.json                         metadata TAP de la observación
    cutouts/<obs_id>/<ra>_<dec>_<size>.npz    IMAGE, VARIANCE, ZODI, FLAGS, λ, header
"""
from __future__ import annotations

import io
import json
import logging
import threading
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS, FITSFixedWarning

from . import irsa
from .settings import Settings, get_settings

log = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=FITSFixedWarning)
logging.getLogger("astropy").setLevel(logging.ERROR)  # aviso repetido de SIP en el WCS alterno "W"

_HEADER_SKIP = {"HISTORY", "COMMENT", ""}
CUTOUT_PAD = 1.45
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


@dataclass
class Cutout:
    image: np.ndarray        # MJy/sr
    variance: np.ndarray
    zodi: np.ndarray
    flags: np.ndarray        # int32, bitmap
    wave_um: np.ndarray      # λ central por píxel
    bandwidth_um: np.ndarray
    header: fits.Header      # header de IMAGE (WCS espacial + metadata)
    flag_bits: dict[str, int]  # nombre -> bit, leído de MP_* del header de FLAGS

    @property
    def wcs(self) -> WCS:
        return WCS(self.header)

    def wavelength_at(self, ra: float, dec: float) -> float | None:
        x, y = self.wcs.all_world2pix([[ra, dec]], 0)[0]
        j, i = int(round(float(x))), int(round(float(y)))
        if 0 <= i < self.wave_um.shape[0] and 0 <= j < self.wave_um.shape[1]:
            v = float(self.wave_um[i, j])
            return v if np.isfinite(v) else None
        return None


def cutout_key(obs_id: str, ra: float, dec: float, size_deg: float) -> str:
    return f"{obs_id}/{ra:.5f}_{dec:+.5f}_{size_deg:.4f}"


def _path(key: str, s: Settings) -> Path:
    return s.cache_dir / "cutouts" / f"{key}.npz"


def _lock(key: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


# ---------- metadata de observaciones (para resolver id -> uri sin volver a IRSA) ----------

def save_observations(observations: list[irsa.Observation], s: Settings | None = None) -> None:
    s = s or get_settings()
    d = s.cache_dir / "obs"
    d.mkdir(parents=True, exist_ok=True)
    for o in observations:  # se reescribe: la ficha puede ganar campos (p. ej. collection)
        (d / f"{o.id}.json").write_text(json.dumps(o.to_dict()))


def load_observation(obs_id: str, s: Settings | None = None) -> irsa.Observation | None:
    s = s or get_settings()
    p = s.cache_dir / "obs" / f"{Path(obs_id).name}.json"
    return irsa.Observation(**json.loads(p.read_text())) if p.exists() else None


# ---------- cutouts ----------

def compact_from_fits(raw: bytes) -> Cutout:
    """MEF de IRSA -> Cutout compacto (descarta la PSF)."""
    with fits.open(io.BytesIO(raw)) as h:
        hdr = h["IMAGE"].header
        ny, nx = h["IMAGE"].data.shape
        wave_wcs = WCS(hdr, fobj=h, key="W")
        wave_wcs.sip = None
        yy, xx = np.mgrid[0:ny, 0:nx]
        wave, bw = wave_wcs.pixel_to_world_values(xx, yy)
        # wcslib entrega λ en metros (SI) aunque CUNIT diga um
        scale = 1e6 if np.nanmedian(wave) < 1e-3 else 1.0
        clean = fits.Header([c for c in hdr.cards if c.keyword not in _HEADER_SKIP])
        flag_bits = {
            k[3:]: int(v) for k, v in h["FLAGS"].header.items() if k.startswith("MP_")
        }
        return Cutout(
            image=np.asarray(h["IMAGE"].data, dtype=np.float32),
            variance=np.asarray(h["VARIANCE"].data, dtype=np.float32),
            zodi=np.asarray(h["ZODI"].data, dtype=np.float32),
            flags=np.asarray(h["FLAGS"].data, dtype=np.int32),
            wave_um=(wave * scale).astype(np.float32),
            bandwidth_um=(bw * scale).astype(np.float32),
            header=clean,
            flag_bits=flag_bits,
        )


def _save(c: Cutout, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(
        tmp, image=c.image, variance=c.variance, zodi=c.zodi, flags=c.flags,
        wave_um=c.wave_um, bandwidth_um=c.bandwidth_um,
        header=np.array(c.header.tostring()), flag_bits=np.array(json.dumps(c.flag_bits)),
    )
    tmp.replace(path)  # atómico: nunca queda un archivo a medias


def _load(path: Path) -> Cutout:
    with np.load(path) as z:
        return Cutout(
            image=z["image"], variance=z["variance"], zodi=z["zodi"], flags=z["flags"],
            wave_um=z["wave_um"], bandwidth_um=z["bandwidth_um"],
            header=fits.Header.fromstring(str(z["header"])),
            flag_bits=json.loads(str(z["flag_bits"])),
        )


def get_cached(obs_id: str, ra: float, dec: float, size_deg: float,
               s: Settings | None = None) -> Cutout | None:
    s = s or get_settings()
    p = _path(cutout_key(obs_id, ra, dec, size_deg), s)
    return _load(p) if p.exists() else None


_wave_memo: dict[str, float | None] = {}


def cached_wavelength(obs_id: str, ra: float, dec: float, size_deg: float,
                      s: Settings | None = None) -> tuple[bool, float | None]:
    """(¿está en caché?, λ en el objetivo) sin abrir el .npz más de una vez por proceso."""
    s = s or get_settings()
    key = f"{s.cache_dir}/{cutout_key(obs_id, ra, dec, size_deg)}"
    if key in _wave_memo:
        return True, _wave_memo[key]
    c = get_cached(obs_id, ra, dec, size_deg, s)
    if c is None:
        return False, None
    _wave_memo[key] = lam = c.wavelength_at(ra, dec)  # los .npz no cambian una vez escritos
    return True, lam


def get_cutout(obs: irsa.Observation, ra: float, dec: float, size_deg: float,
               s: Settings | None = None) -> Cutout:
    """Devuelve el cutout desde caché; si no está, lo baja de IRSA una sola vez."""
    s = s or get_settings()
    key = cutout_key(obs.id, ra, dec, size_deg)
    path = _path(key, s)
    with _lock(key):
        if path.exists():
            return _load(path)
        log.info("IRSA cutout %s", key)
        # El cutout viene en ejes del detector (rotado): se pide √2 más grande para que
        # el cuadro north-up de lado size_deg quede lleno, sin esquinas vacías.
        c = compact_from_fits(irsa.fetch_cutout(obs.uri, ra, dec, size_deg * CUTOUT_PAD, s))
        _save(c, path)
        return c
