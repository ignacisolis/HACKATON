"""Carga config/release.yaml. Ningún otro módulo conoce el release ni las URLs de IRSA."""
from __future__ import annotations

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
    cache_dir: Path


def load_settings(path: Path | str | None = None) -> Settings:
    path = Path(path) if path else config_path()
    cfg = yaml.safe_load(path.read_text())
    rel, irsa, cut = cfg["release"], cfg["irsa"], cfg["cutout"]
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
        cache_dir=cache_dir,
    )


@lru_cache
def get_settings() -> Settings:
    return load_settings()
