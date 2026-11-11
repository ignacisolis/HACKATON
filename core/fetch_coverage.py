"""Mide la cobertura de SPHEREx sobre cada objetivo. Escribe config/coverage.yaml.

Rol C (Ciencia) - tarea 7 del Tablero.

Que contesta
------------
Cuantas observaciones hay sobre cada objetivo, en cuantas fechas distintas, con
que detectores y en que rango de longitud de onda. De eso depende si el "video"
de una sola banda tiene suficientes cuadros, que es la pregunta que decide la
interfaz del reproductor.

Importante: consulta la posicion PROPAGADA a la ventana de SPHEREx, no la de
catalogo. Para WISE 0855 son 34 pixeles de diferencia (ver core/targets.py).

Uso:
    python core/fetch_coverage.py                 # los 4 objetivos
    python core/fetch_coverage.py wise_0855       # uno solo
    python core/fetch_coverage.py --dry-run

Red: IRSA TAP. Lento, ~15-30 s por objetivo. Necesita certifi para el TLS.
"""
from __future__ import annotations

import argparse
import csv
import io
import socket
import ssl
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import certifi
import numpy as np
import yaml
from astropy.time import Time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import targets as tg  # noqa: E402

IRSA_TAP = "https://irsa.ipac.caltech.edu/TAP/sync"
TIMEOUT_S = 300

# Epoca a la que se propaga el objetivo para preguntar la cobertura. Se usa el
# medio de la ventana: dentro de la ventana el objeto se mueve mucho menos que
# el campo de un detector, asi que para CONTAR observaciones alcanza.
QUERY_EPOCH = "2025-11-09"

# Canales espectrales por detector. 6 detectores x 17 = las 102 bandas de la
# mision. Se usa para estimar cuantas epocas caen por banda, que es la pregunta
# que decide si el video de una sola banda tiene suficientes cuadros.
#
# ES UNA ESTIMACION, y hay que decirlo: reparte las observaciones del detector
# en partes iguales entre sus 17 canales. En la realidad depende de donde cae el
# objetivo en el detector cada vez, que no es uniforme. El numero exacto por
# banda sale de leer WCS-WAVE de cada recorte (tarea 23).
CHANNELS_PER_DETECTOR = 17


def tap_csv(adql):
    """Consulta ADQL sincrona contra IRSA, devuelve filas como dicts."""
    socket.setdefaulttimeout(TIMEOUT_S)
    ctx = ssl.create_default_context(cafile=certifi.where())
    body = urllib.parse.urlencode({
        "REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": adql,
    }).encode()
    req = urllib.request.Request(
        IRSA_TAP, data=body, headers={"User-Agent": "spherex-visor/0.1 (hackathon)"},
    )
    with urllib.request.urlopen(req, context=ctx) as resp:
        text = resp.read().decode()
    return list(csv.DictReader(io.StringIO(text)))


COVERAGE_QUERY = """
SELECT p.planeid, p.energy_bandpassname, p.time_bounds_lower, p.time_bounds_upper,
       p.energy_bounds_lower, p.energy_bounds_upper, p.energy_dimension,
       p.energy_resolvingpower, p.position_samplesize, p.quality_flag,
       p.provenance_version, a.producttype
FROM spherex.artifact a
JOIN spherex.plane p ON a.planeid = p.planeid
WHERE 1 = CONTAINS(POINT('ICRS', {ra}, {dec}), p.poly)
ORDER BY p.time_bounds_lower
"""


def fnum(row, key):
    """float o None, tolerando celdas vacias del CSV."""
    v = (row.get(key) or "").strip()
    try:
        return float(v)
    except ValueError:
        return None


def coverage_for(key):
    """Mide la cobertura de un objetivo en su posicion propagada."""
    ra, dec = tg.target_position(key, QUERY_EPOCH)
    rows = tap_csv(COVERAGE_QUERY.format(ra=ra, dec=dec))

    # Un plane puede traer varios artifacts. Lo que cuenta como "observacion" es
    # el plane; contar filas infla el numero.
    planes = {}
    producttypes = Counter()
    for r in rows:
        producttypes[(r.get("producttype") or "").strip()] += 1
        planes.setdefault(r["planeid"], r)

    mjds = np.array([fnum(r, "time_bounds_lower") for r in planes.values()], dtype=float)
    mjds = mjds[~np.isnan(mjds)]
    dates = sorted({Time(m, format="mjd").isot[:10] for m in mjds}) if mjds.size else []

    per_detector = defaultdict(list)
    for r in planes.values():
        per_detector[(r.get("energy_bandpassname") or "?").strip()].append(r)

    detectors = {}
    for det in sorted(per_detector):
        sub = per_detector[det]
        dm = np.array([fnum(r, "time_bounds_lower") for r in sub], dtype=float)
        dm = dm[~np.isnan(dm)]
        lo = [fnum(r, "energy_bounds_lower") for r in sub]
        hi = [fnum(r, "energy_bounds_upper") for r in sub]
        lo = [v for v in lo if v is not None]
        hi = [v for v in hi if v is not None]
        dim = [fnum(r, "energy_dimension") for r in sub]
        dim = [v for v in dim if v is not None]
        rp = [fnum(r, "energy_resolvingpower") for r in sub]
        rp = [v for v in rp if v is not None]
        detectors[det] = {
            "observations": len(sub),
            "obs_per_channel_est": round(len(sub) / CHANNELS_PER_DETECTOR, 1),
            "distinct_dates": len({Time(m, format="mjd").isot[:10] for m in dm}),
            "first": Time(dm.min(), format="mjd").isot[:10] if dm.size else None,
            "last": Time(dm.max(), format="mjd").isot[:10] if dm.size else None,
            # metros -> micrometros
            "wavelength_min_um": round(min(lo) * 1e6, 4) if lo else None,
            "wavelength_max_um": round(max(hi) * 1e6, 4) if hi else None,
            "energy_dimension": int(max(dim)) if dim else None,
            "resolving_power": round(float(np.median(rp)), 1) if rp else None,
        }

    releases = sorted({(r.get("provenance_version") or "").strip()
                       for r in planes.values()} - {""})
    quality = Counter((r.get("quality_flag") or "").strip() for r in planes.values())

    return {
        "label": tg.get_target(key)["label"],
        "queried_at": {
            "epoch": QUERY_EPOCH,
            "ra_deg": round(ra, 6),
            "dec_deg": round(dec, 6),
            "note": "posicion propagada por movimiento propio, no la de catalogo",
        },
        "observations": len(planes),
        "artifact_rows": len(rows),
        "producttypes": dict(producttypes),
        "distinct_dates": len(dates),
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "detectors_covering": len(detectors),
        "detectors": detectors,
        "releases": releases,
        "quality_flags": {k or "(vacio)": v for k, v in quality.items()},
        "dates": dates,
    }


def markdown_table(cov):
    """Tabla resumen por objetivo, para pegar en docs/ciencia.md."""
    out = ["| Objetivo | Obs. | Fechas | Rango | Detectores | Obs./fecha |",
           "|---|---|---|---|---|---|"]
    for key, c in cov.items():
        per_date = c["observations"] / c["distinct_dates"] if c["distinct_dates"] else 0
        rango = (c["first_date"] or "?") + " → " + (c["last_date"] or "?")
        out.append("| **" + c["label"] + "** | " + str(c["observations"]) + " | "
                   + str(c["distinct_dates"]) + " | " + rango + " | "
                   + str(c["detectors_covering"]) + "/6 | "
                   + format(per_date, ".1f") + " |")
    return "\n".join(out)


def markdown_detectors(cov):
    """Detalle por detector: cuantas epocas y en que longitud de onda."""
    out = []
    for key, c in cov.items():
        out.append("\n**" + c["label"] + "**\n")
        out.append("| Detector | λ (µm) | R | Obs. | Fechas | Obs./banda (est.) |")
        out.append("|---|---|---|---|---|---|")
        for det, d in c["detectors"].items():
            lam = "?"
            if d["wavelength_min_um"] is not None:
                lam = format(d["wavelength_min_um"], ".2f") + "–" + format(d["wavelength_max_um"], ".2f")
            out.append("| " + det.replace("SPHEREx-", "") + " | " + lam + " | "
                       + str(d["resolving_power"] or "?") + " | "
                       + str(d["observations"]) + " | " + str(d["distinct_dates"]) + " | "
                       + format(d["obs_per_channel_est"], ".1f") + " |")
    return "\n".join(out)


def main():
    # La consola de Windows usa cp1252 y se ahoga con las flechas y guiones de
    # las tablas. El archivo ya se escribe en utf-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    ap = argparse.ArgumentParser(description="Mide la cobertura de SPHEREx por objetivo.")
    ap.add_argument("targets", nargs="*", help="claves; por defecto los 4")
    ap.add_argument("--out", default="config/coverage.yaml")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    keys = args.targets or tg.target_keys()
    cov = {}
    for key in keys:
        ra, dec = tg.target_position(key, QUERY_EPOCH)
        print("Consultando " + key + " en " + format(ra, ".5f") + ", "
              + format(dec, ".5f") + " ...", flush=True)
        cov[key] = coverage_for(key)
        c = cov[key]
        print("  " + str(c["observations"]) + " observaciones, "
              + str(c["distinct_dates"]) + " fechas, "
              + str(c["detectors_covering"]) + "/6 detectores", flush=True)

    print("\n" + markdown_table(cov))
    print(markdown_detectors(cov))

    if args.dry_run:
        return
    doc = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "core/fetch_coverage.py",
        "irsa_endpoint": IRSA_TAP,
        "query_epoch": QUERY_EPOCH,
        "coverage": cov,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        fh.write("# config/coverage.yaml - GENERADO por core/fetch_coverage.py\n")
        fh.write("# Cobertura de SPHEREx sobre cada objetivo, en su posicion propagada.\n\n")
        yaml.dump(doc, fh, allow_unicode=True, sort_keys=False, default_flow_style=False,
                  width=100)
    print("\nEscrito " + str(out))


if __name__ == "__main__":
    main()
