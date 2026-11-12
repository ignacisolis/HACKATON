"""Único módulo que habla con IRSA (TAP + cutouts).

Si IRSA cambia su API o sus tablas, solo se toca este archivo y config/release.yaml.
"""
from __future__ import annotations

import csv
import io
import logging
import random
import re
import threading
import time
from dataclasses import asdict, dataclass

import httpx

from .settings import Settings, get_settings

log = logging.getLogger(__name__)

# ---------- reintentos con espera compartida ----------
# IRSA corta con 503 después de ~15 descargas seguidas (Nacho, Bitácora 11-nov). Cuando
# un hilo recibe 503/429, TODOS los hilos esperan (pausa compartida) en vez de seguir
# golpeando; la espera crece exponencialmente y respeta Retry-After si IRSA lo manda.
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 6
BASE_DELAY_S = 2.0
MAX_DELAY_S = 60.0

_pause_until = 0.0
_pause_lock = threading.Lock()


def _wait_for_pause() -> None:
    while True:
        with _pause_lock:
            remaining = _pause_until - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 5.0))


def _pause_all(seconds: float) -> None:
    global _pause_until
    with _pause_lock:
        _pause_until = max(_pause_until, time.monotonic() + seconds)


def _retry_after(r: httpx.Response | None) -> float | None:
    try:
        return float(r.headers["Retry-After"]) if r is not None else None
    except (KeyError, ValueError):
        return None


def backoff_delay(attempt: int, retry_after: float | None = None) -> float:
    """Espera antes del intento `attempt` (0 = primero que falló): 2, 4, 8, 16, 32, 60 s ± 25 %."""
    if retry_after is not None:
        return min(MAX_DELAY_S, retry_after)
    d = min(MAX_DELAY_S, BASE_DELAY_S * 2 ** attempt)
    return d * random.uniform(0.75, 1.25)


def _request(method: str, url: str, s: Settings, what: str, **kw) -> httpx.Response:
    """GET/POST a IRSA con reintentos; los errores 4xx que no son 429 no se reintentan."""
    last: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        _wait_for_pause()
        r = None
        try:
            r = httpx.request(method, url, timeout=s.timeout_s, follow_redirects=True, **kw)
            if r.status_code in RETRY_STATUS:
                raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as e:
            last = e
            if e.response.status_code not in RETRY_STATUS:
                break
            delay = backoff_delay(attempt, _retry_after(e.response))
            if e.response.status_code in (429, 503):
                _pause_all(delay)  # IRSA pide aire: frenan todos los hilos
        except httpx.TransportError as e:  # timeouts, conexión cortada
            last = e
            delay = backoff_delay(attempt)
        if attempt < MAX_ATTEMPTS - 1:
            log.info("%s: %s; reintento %d en %.0f s", what, last, attempt + 1, delay)
            time.sleep(delay)
    raise IrsaError(f"{what} falló tras {MAX_ATTEMPTS} intentos: {last}")

_FILE_RE = re.compile(r"level2_(?P<id>.+?)_spx_(?P<version>l2b-v\d+-\d{4}-\d+)\.fits$")
_DID_RE = re.compile(r"^ivo://irsa\.ipac/(?P<collection>[A-Za-z0-9_]+)\?")
_COLLECTION_OK = re.compile(r"^[A-Za-z0-9_]+$")


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
    collection: str = ""  # p. ej. "spherex_qr2" o "spherex_qr3_deep"

    def to_dict(self) -> dict:
        return asdict(self)


class IrsaError(RuntimeError):
    pass


def _tap(query: str, s: Settings) -> list[dict]:
    r = _request("POST", s.tap_url, s, "TAP de IRSA", data={"QUERY": query, "FORMAT": "csv"})
    if r.text.lstrip().startswith("<"):  # IRSA devuelve VOTable de error aunque se pida CSV
        raise IrsaError(f"TAP de IRSA devolvió un error: {r.text[:500]}")
    return list(csv.DictReader(io.StringIO(r.text)))


def _collection_filter(s: Settings) -> str:
    for c in s.collections:
        if not _COLLECTION_OK.match(c):
            raise ValueError(f"nombre de colección inválido en config: {c!r}")
    ors = " OR ".join(f"p.obs_publisher_did LIKE 'ivo://irsa.ipac/{c}?%'" for c in s.collections)
    return f"({ors})"


def build_query(ra: float, dec: float, s: Settings) -> str:
    ra, dec = float(ra), float(dec)  # nunca se interpola texto del usuario en ADQL
    return f"""
    SELECT a.uri, a.contentlength, p.obs_publisher_did,
           p.time_bounds_lower, p.time_bounds_upper, p.time_exposure,
           p.energy_bandpassname, p.energy_bounds_lower, p.energy_bounds_upper
    FROM {s.artifact_table} a
    JOIN {s.plane_table} p ON a.planeid = p.planeid
    WHERE 1 = CONTAINS(POINT('ICRS', {ra!r}, {dec!r}), p.poly)
      AND a.producttype = 'science'
      AND {_collection_filter(s)}
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
            collection=_collection_of(row.get("obs_publisher_did")),
        )
        prev = by_id.get(obs.id)
        if prev is None or _version_key(obs.version) > _version_key(prev.version):
            by_id[obs.id] = obs
    return sorted(by_id.values(), key=lambda o: (o.mjd_start, o.detector))


def _float_or_none(v: str | None) -> float | None:
    return float(v) if v not in (None, "") else None


def _collection_of(did: str | None) -> str:
    m = _DID_RE.match(did or "")
    return m["collection"] if m else ""


def _version_key(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def query_observations(ra: float, dec: float, s: Settings | None = None) -> list[Observation]:
    """Observaciones de SPHEREx cuyo campo contiene (ra, dec), ordenadas por fecha."""
    s = s or get_settings()
    return parse_rows(_tap(build_query(ra, dec, s), s), s)


def list_collections(s: Settings | None = None) -> list[dict]:
    """Colecciones SPHEREx publicadas en IRSA, con nº de planos y rango de fechas (MJD). Tarda ~1 min."""
    s = s or get_settings()
    rows = _tap(f"""
    SELECT obs_collection, COUNT(*) AS n, MIN(t_min) AS mjd_min, MAX(t_max) AS mjd_max
    FROM {s.obscore_table} GROUP BY obs_collection
    """, s)
    return sorted(
        ({"collection": r["obs_collection"], "n": int(r["n"]),
          "mjd_min": _float_or_none(r["mjd_min"]), "mjd_max": _float_or_none(r["mjd_max"])} for r in rows),
        key=lambda r: (r["mjd_min"] is None, r["mjd_min"] or 0),  # las colecciones sin fechas (cal) al final
    )


def cutout_url(obs_uri: str, ra: float, dec: float, size_deg: float, s: Settings | None = None) -> str:
    s = s or get_settings()
    return f"{s.data_base_url}{obs_uri}?center={float(ra)!r},{float(dec)!r}d&size={float(size_deg)!r}"


def fetch_cutout(obs_uri: str, ra: float, dec: float, size_deg: float,
                 s: Settings | None = None) -> bytes:
    """Descarga el cutout MEF (FITS) de una observación, con reintentos y espera compartida."""
    s = s or get_settings()
    url = cutout_url(obs_uri, ra, dec, size_deg, s)
    r = _request("GET", url, s, f"cutout {obs_uri.rsplit('/', 1)[-1]}")
    if not r.content.startswith(b"SIMPLE"):
        raise IrsaError(f"IRSA no devolvió un FITS para {url}: {r.content[:200]!r}")
    return r.content
