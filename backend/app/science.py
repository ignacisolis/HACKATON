"""Puente entre backend/ y core/ (rol C · Nacho).

Todo lo científico se delega a core/: posiciones con movimiento propio (core.targets),
máscaras y conteos de FLAGS (core.flags), espectros (core.extract_spectrum). Este
módulo solo traduce entre la caché del backend y los tipos de core.datatypes.
"""
from __future__ import annotations

import math
import sys
from functools import lru_cache

import numpy as np
from astropy.time import Time

from .settings import REPO_ROOT

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import core  # noqa: E402
from core import flags as core_flags  # noqa: E402
from core import targets as core_targets  # noqa: E402
from core.datatypes import Frame  # noqa: E402

from .cache import Cutout  # noqa: E402
from .irsa import Observation  # noqa: E402

PHOTOMETRY = "photometry"  # máscara que NO borra SOURCE (ver contracts/api.md)


# ---------- objetivos (core.targets) ----------

def target_keys() -> list[str]:
    return core_targets.target_keys()


def target_label(key: str) -> str:
    return core_targets.get_target(key).get("label", key)


@lru_cache
def window_mjd() -> tuple[float, float]:
    w = core_targets.load_config()["spherex_window"]
    return Time(str(w[0])).mjd, Time(str(w[1])).mjd


@lru_cache(maxsize=32)
def _edges(key: str) -> tuple[float, tuple[float, float], float, tuple[float, float]]:
    a, b = window_mjd()
    return a, core_targets.target_position(key, a), b, core_targets.target_position(key, b)


def target_radec(key: str, mjd: float) -> tuple[float, float]:
    """Posición del objetivo en `mjd`.

    Interpola entre las posiciones que da core.targets en los bordes de la ventana de
    SPHEREx: el movimiento propio es lineal y en 1.5 años el error es < 0.001″
    (test_science.py lo compara con core.targets.target_position). Así 2483 cuadros
    de R Dra se resuelven en milisegundos en vez de ~5 s.
    """
    a, (ra0, dec0), b, (ra1, dec1) = _edges(key)
    t = (mjd - a) / (b - a)
    dra = (ra1 - ra0 + 180.0) % 360.0 - 180.0
    return (ra0 + t * dra) % 360.0, dec0 + t * (dec1 - dec0)


def window_center(key: str) -> tuple[float, float, str]:
    """Centro del recorte para un objetivo: su posición a mitad de la ventana."""
    a, b = window_mjd()
    mid = (a + b) / 2
    ra, dec = target_radec(key, mid)
    return round(float(ra), 5), round(float(dec), 5), Time(mid, format="mjd").isot[:10]


# ---------- cuadros (core.datatypes.Frame) ----------

def frame_mjd(c: Cutout | None, obs: Observation) -> float:
    """MJD-AVG del header (lo que usa core/); sin cutout, el punto medio de TAP."""
    if c is not None and c.header.get("MJD-AVG") is not None:
        return float(c.header["MJD-AVG"])
    return (obs.mjd_start + obs.mjd_end) / 2


def position_at(key: str | None, ra: float, dec: float, mjd: float) -> tuple[float, float]:
    return target_radec(key, mjd) if key else (ra, dec)


def to_frame(c: Cutout, obs: Observation, key: str | None, ra: float, dec: float) -> Frame:
    """Cutout cacheado -> core.Frame (sin PSF), con λ y ancho en la posición del objetivo."""
    mjd = frame_mjd(c, obs)
    wcs = c.wcs
    x, y = wcs.world_to_pixel_values(*position_at(key, ra, dec, mjd))
    i, j = int(round(float(y))), int(round(float(x)))
    inside = 0 <= i < c.image.shape[0] and 0 <= j < c.image.shape[1]
    return Frame(
        image=c.image, flags=c.flags.astype(np.uint32), variance=c.variance, wcs=wcs,
        mjd=mjd, detector=f"D{obs.detector}",
        wavelength_um=float(c.wave_um[i, j]) if inside else math.nan,
        bandwidth_um=float(c.bandwidth_um[i, j]) if inside else math.nan,
        zodi=c.zodi, release=obs.version, meta={"id": obs.id, "collection": obs.collection},
    )


# ---------- FLAGS (core.flags) ----------

def flagged_fraction(flags: np.ndarray) -> float:
    """Fracción del recorte que la máscara de fotometría excluye."""
    return round(float(np.mean(core_flags.mask_for(flags, PHOTOMETRY))), 4)


def quality(c: Cutout, inside: bool, target_masked: bool, frac: float) -> str:
    """'ok' | 'suspect' | 'bad', con las mismas palabras que SpectrumPoint.quality."""
    if not inside or str(c.header.get("L2DQAFLG", "Pass")).strip() != "Pass":
        return "bad"
    if target_masked or frac > 0.5:
        return "suspect"
    return "ok"


def flags_report(c: Cutout) -> dict:
    """Bloque `flags` de /meta según contracts/api.md."""
    present = core_flags.bit_counts(c.flags)
    return {
        "extension_is_mask": True,
        "cutout_counts": present,
        "full_frame_counts": core_flags.pipeline_counts(c.header),
        "undocumented_bits_present": core_flags.undocumented_bits_present(c.flags),
    }


def mask_layers(c: Cutout) -> list[str]:
    return [r["name"] for r in core_flags.bit_counts(c.flags)]


def bit_of(name_or_bit: str) -> int:
    return int(name_or_bit) if str(name_or_bit).isdigit() else core_flags.bit_of(str(name_or_bit))


# ---------- espectros (core.extract_spectrum, tarea 23) ----------

def extract_spectrum(frames: list[Frame], key: str | None, ra: float, dec: float):
    kw = {"target_key": key} if key else {"ra": ra, "dec": dec}
    return core.extract_spectrum(frames, mask_purpose=PHOTOMETRY, **kw)


def combine(points):
    return core.combine(points)


def light_curve(points, band: int):
    # core.light_curve filtra por numero de banda (1..102). Antes recibia
    # band_um + tolerance_um, que era la firma del stub; Nacho la cambio al
    # implementarla en la tarea 23, porque el numero de banda ya identifica
    # el canal y evita mezclar longitudes de onda sin darse cuenta.
    return core.light_curve(points, band=band)


DEFAULT_APERTURE_PX = core.spectrum.DEFAULT_APERTURE_PX
