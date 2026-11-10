"""Único módulo que habla con IRSA (TAP + cutouts).

Si IRSA cambia su API o sus tablas, solo se toca este archivo y config/release.yaml.
"""
from __future__ import annotations

import csv
import io
import re
import time
from dataclasses import asdict, dataclass

import httpx

from .settings import Settings, get_settings

_FILE_RE = re.compile(r"level2_(?P<id>.+?)_spx_(?P<version>l2b-v\d+-\d{4}-\d+)\.fits$")


@dataclass(frozen=True)
class Observation:
    id: str            # p. ej. "2025W19_1B_0116_1D3" (exposición + detector)
    uri: str           # ruta relativa en IRSA (ibe/data/spherex/...)
    version: str       # versión de procesamiento, p. ej. "l2b-v20-2025-241"
    detector: int      # 1..6
    mjd_start: float
    mjd_end: float
    exposure_s: float
    lambda_min_um: float
    lambda_max_um: float
    size_bytes: int

    def to_dict(self) -> dict:
        return asdict(self)


class IrsaError(RuntimeError):
    pass


def _tap(query: str, s: Settings) -> list[dict]:
    try:
        r = httpx.post(s.tap_url, data={"QUERY": query, "FORMAT": "csv"}, timeout=s.timeout_s)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise IrsaError(f"TAP de IRSA falló: {e}") from e
    if r.text.lstrip().startswith("<"):  # IRSA devuelve VOTable de error aunque se pida CSV
        raise IrsaError(f"TAP de IRSA devolvió un error: {r.text[:500]}")
    return list(csv.DictReader(io.StringIO(r.text)))


def build_query(ra: float, dec: float, s: Settings) -> str:
    ra, dec = float(ra), float(dec)  # nunca se interpola texto del usuario en ADQL
    return f"""
    SELECT a.uri, a.contentlength,
           p.time_bounds_lower, p.time_bounds_upper, p.time_exposure,
           p.energy_bandpassname, p.energy_bounds_lower, p.energy_bounds_upper
    FROM {s.artifact_table} a
    JOIN {s.plane_table} p ON a.planeid = p.planeid
    WHERE 1 = CONTAINS(POINT('ICRS', {ra!r}, {dec!r}), p.poly)
      AND a.producttype = 'science'
      AND a.uri LIKE '%/spherex/{s.release_name}/%'
    ORDER BY p.time_bounds_lower
    """


def parse_rows(rows: list[dict], s: Settings) -> list[Observation]:
    """Filas TAP -> Observaciones. Si una exposición aparece en varias versiones, queda la más nueva."""
    by_id: dict[str, Observation] = {}
    for row in rows:
        m = _FILE_RE.search(row["uri"])
        if not m:
            continue
        version = m["version"]
        if s.release_versions and version not in s.release_versions:
            continue
        obs = Observation(
            id=m["id"],
            uri=row["uri"],
            version=version,
            detector=int(row["energy_bandpassname"].rsplit("D", 1)[-1]),
            mjd_start=float(row["time_bounds_lower"]),
            mjd_end=float(row["time_bounds_upper"]),
            exposure_s=float(row["time_exposure"] or 0),
            lambda_min_um=float(row["energy_bounds_lower"]) * 1e6,
            lambda_max_um=float(row["energy_bounds_upper"]) * 1e6,
            size_bytes=int(row["contentlength"] or 0),
        )
        prev = by_id.get(obs.id)
        if prev is None or _version_key(obs.version) > _version_key(prev.version):
            by_id[obs.id] = obs
    return sorted(by_id.values(), key=lambda o: (o.mjd_start, o.detector))


def _version_key(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def query_observations(ra: float, dec: float, s: Settings | None = None) -> list[Observation]:
    """Observaciones de SPHEREx cuyo campo contiene (ra, dec), ordenadas por fecha."""
    s = s or get_settings()
    return parse_rows(_tap(build_query(ra, dec, s), s), s)


def cutout_url(obs_uri: str, ra: float, dec: float, size_deg: float, s: Settings | None = None) -> str:
    s = s or get_settings()
    return f"{s.data_base_url}{obs_uri}?center={float(ra)!r},{float(dec)!r}d&size={float(size_deg)!r}"


def fetch_cutout(obs_uri: str, ra: float, dec: float, size_deg: float,
                 s: Settings | None = None, retries: int = 2) -> bytes:
    """Descarga el cutout MEF (FITS) de una observación. Reintenta errores transitorios."""
    s = s or get_settings()
    url = cutout_url(obs_uri, ra, dec, size_deg, s)
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = httpx.get(url, timeout=s.timeout_s, follow_redirects=True)
            r.raise_for_status()
            if not r.content.startswith(b"SIMPLE"):
                raise IrsaError(f"IRSA no devolvió un FITS para {url}: {r.content[:200]!r}")
            return r.content
        except (httpx.HTTPError, IrsaError) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise IrsaError(f"cutout falló tras {retries + 1} intentos: {last}")
