"""Carga config/release.yaml. Ningún otro módulo conoce el release ni las URLs de IRSA."""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "release.yaml"


def config_path() -> Path:
    return Path(os.environ.get("SPHEREX_CONFIG", DEFAULT_CONFIG))


@dataclass(frozen=True)
class Settings:
    collections: tuple[str, ...]
    release_label: str
    release_versions: tuple[str, ...]
    tap_url: str
    data_base_url: str
    plane_table: str
    artifact_table: str
    obscore_table: str
    timeout_s: float
    max_workers: int
    default_size_deg: float
    max_size_deg: float
    channels_per_detector: int
    detectors_um: dict[int, tuple[float, float]]
    cache_dir: Path

    def band_of(self, detector: int, wavelength_um: float) -> int | None:
        """Banda 1..102 aproximada: canal log-espaciado dentro del rango del detector."""
        lo, hi = self.detectors_um[detector]
        # El λ por píxel (WCS-WAVE) puede salirse ~1 % del rango TAP del detector: se lleva al borde.
        if not (lo * 0.98 <= wavelength_um <= hi * 1.02):
            return None
        n = self.channels_per_detector
        frac = (math.log(wavelength_um) - math.log(lo)) / (math.log(hi) - math.log(lo))
        channel = min(max(int(frac * n), 0), n - 1)
        return (detector - 1) * n + channel + 1

    def band_range_um(self, band: int) -> tuple[int, float, float]:
        """Inverso de band_of: (detector, λmin, λmax) de una banda 1..102."""
        n = self.channels_per_detector
        if not 1 <= band <= n * len(self.detectors_um):
            raise ValueError(f"banda fuera de rango: {band}")
        detector, channel = divmod(band - 1, n)
        detector += 1
        lo, hi = self.detectors_um[detector]
        step = (math.log(hi) - math.log(lo)) / n
        return detector, math.exp(math.log(lo) + channel * step), math.exp(math.log(lo) + (channel + 1) * step)


def load_settings(path: Path | str | None = None) -> Settings:
    path = Path(path) if path else config_path()
    cfg = yaml.safe_load(path.read_text())
    rel, irsa, cut, bands = cfg["release"], cfg["irsa"], cfg["cutout"], cfg["bands"]
    cache_dir = Path(os.environ.get("SPHEREX_CACHE_DIR", cfg["cache"]["dir"]))
    if not cache_dir.is_absolute():
        cache_dir = REPO_ROOT / cache_dir
    return Settings(
        collections=tuple(rel["collections"]),
        release_label=rel.get("label", ", ".join(rel["collections"])),
        release_versions=tuple(rel.get("versions") or ()),
        tap_url=irsa["tap_url"],
        data_base_url=irsa["data_base_url"].rstrip("/") + "/",
        plane_table=irsa["plane_table"],
        artifact_table=irsa["artifact_table"],
        obscore_table=irsa.get("obscore_table", "spherex.obscore"),
        timeout_s=float(irsa.get("timeout_s", 180)),
        max_workers=int(irsa.get("max_workers", 8)),
        default_size_deg=float(cut["default_size_deg"]),
        max_size_deg=float(cut["max_size_deg"]),
        channels_per_detector=int(bands["channels_per_detector"]),
        detectors_um={int(k): (float(v[0]), float(v[1])) for k, v in bands["detectors_um"].items()},
        cache_dir=cache_dir,
    )


@lru_cache
def get_settings() -> Settings:
    return load_settings()
