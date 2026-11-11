"""Regenera config/targets.yaml consultando SIMBAD.

Rol C (Ciencia) - tarea 6 del Tablero.

Por que existe: las coordenadas del enunciado del hackathon son de la epoca de
descubrimiento (~2010 para WISE 0855). SPHEREx observa en 2025-2026. Para los
objetos de alto movimiento propio esa diferencia es de decenas de pixeles, asi
que apuntar a las coordenadas del enunciado mide cielo vacio.

Uso:
    python core/fetch_targets.py              # escribe config/targets.yaml
    python core/fetch_targets.py --dry-run    # solo imprime

Red: SIMBAD. El mirror de Harvard es el unico que responde desde la red del
equipo (ver docs/ciencia.md). Necesita el bundle de certifi para el TLS.
"""
from __future__ import annotations

import argparse
import json
import socket
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import certifi
import numpy as np
import yaml
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time

SIMBAD_TAP = "https://simbad.harvard.edu/simbad/sim-tap/sync"
TIMEOUT_S = 90

# Epoca en la que SIMBAD entrega ra/dec de la tabla basic: ICRS, epoca J2000.0.
SIMBAD_COORD_EPOCH = "J2000.0"

# Ventana temporal del archivo de SPHEREx: union de lo que cubre a los 4
# objetivos, medido con core/fetch_coverage.py contra IRSA.
#
# Ojo: cada objetivo tiene su propia ventana, y son distintas (WISE 0855 llega
# solo hasta 2026-05-14). Las ventanas por objetivo estan en config/coverage.yaml.
# Esta de aca es la envolvente, y se usa para acotar la deriva maxima.
SPHEREX_WINDOW = ("2025-04-24", "2026-10-02")

# Escala de placa de SPHEREx: 6.2 arcsec/pixel.
SPHEREX_PIX_ARCSEC = 6.2

# Umbral para decidir si hace falta corregir movimiento propio: medio pixel
# acumulado entre J2000 y el final de la ventana de SPHEREx.
PM_THRESHOLD_ARCSEC = SPHEREX_PIX_ARCSEC / 2

# main_id exacto en SIMBAD -> clave interna del proyecto.
#
# Ojo con dos trampas de nomenclatura:
#   - "* eps Ind B" es el PAR de enanas cafes (Ba+Bb, T1V+T6V), que es lo que
#     pide el enunciado. "* eps Ind b" en minuscula es el planeta: otro objeto.
#   - Para RW Aur usamos "V* RW Aur A", con astrometria de Gaia, y no
#     "V* RW Aur", cuya posicion tiene 3.3 arcsec de error y una paralaje de
#     Hipparcos (15.42 mas) incompatible con la de Gaia (6.41 mas).
TARGETS = {
    "eps_ind_b": {
        "simbad_id": "* eps Ind B",
        "label": "Epsilon Indi B (Ba+Bb)",
        "demo": "par de enanas cafes orbitando una estrella",
    },
    "wise_0855": {
        "simbad_id": "WISEA J085510.74-071442.5",
        "label": "WISE 0855-0714",
        "demo": "movimiento propio muy alto",
    },
    "rw_aur": {
        "simbad_id": "V* RW Aur A",
        "label": "RW Aurigae A",
        "demo": "estrella variable (T Tauri)",
    },
    "r_dra": {
        "simbad_id": "V* R Dra",
        "label": "R Draconis",
        "demo": "variable Mira: brillo y espectro",
    },
}

# Objetos de contexto: no son objetivos de la demo, pero caen en el mismo
# recorte y conviene saber donde estan.
CONTEXT = {
    "eps_ind_a": {
        "simbad_id": "* eps Ind",
        "label": "Epsilon Indi A",
        "note": "la estrella K5V del sistema; contamina el recorte de eps Ind B",
    },
}

# Coordenadas tal como vienen en el enunciado del hackathon, para medir el
# desfase. Solo WISE 0855 trae coordenadas explicitas.
STATEMENT_COORDS = {
    "wise_0855": {"ra": "08h55m10.831s", "dec": "-07d14m42.53s"},
}

BASIC_COLS = [
    "main_id", "otype_txt", "sp_type", "ra", "dec",
    "coo_err_maj", "coo_err_min", "coo_qual", "coo_wavelength", "coo_bibcode",
    "pmra", "pmdec", "pm_err_maj", "pm_err_min", "pm_qual", "pm_bibcode",
    "plx_value", "plx_err", "plx_bibcode", "rvz_radvel", "nbref", "update_date",
]


def tap_query(adql):
    """Ejecuta una consulta ADQL sincrona en SIMBAD y devuelve filas como dicts."""
    socket.setdefaulttimeout(TIMEOUT_S)
    ctx = ssl.create_default_context(cafile=certifi.where())
    body = urllib.parse.urlencode({
        "REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "json", "QUERY": adql,
    }).encode()
    req = urllib.request.Request(
        SIMBAD_TAP, data=body,
        headers={"User-Agent": "spherex-visor/0.1 (hackathon)"},
    )
    with urllib.request.urlopen(req, context=ctx) as resp:
        payload = json.loads(resp.read().decode())
    cols = [c["name"] for c in payload["metadata"]]
    return [dict(zip(cols, row)) for row in payload["data"]]


def fetch_simbad(simbad_ids):
    """Trae la fila de `basic` de cada main_id pedido."""
    quoted = ",".join(repr(str(i)) for i in simbad_ids)
    rows = tap_query(
        "SELECT " + ", ".join(BASIC_COLS) + " FROM basic WHERE main_id IN (" + quoted + ")"
    )
    found = {r["main_id"]: r for r in rows}
    missing = [i for i in simbad_ids if i not in found]
    if missing:
        raise SystemExit("SIMBAD no devolvio: " + repr(missing))
    return found


def to_skycoord(row):
    """SkyCoord en ICRS epoca J2000 con movimiento propio, distancia y RV."""
    kw = dict(
        ra=row["ra"] * u.deg,
        dec=row["dec"] * u.deg,
        pm_ra_cosdec=row["pmra"] * u.mas / u.yr,
        pm_dec=row["pmdec"] * u.mas / u.yr,
        frame="icrs",
        obstime=Time("J2000.0"),
    )
    plx = row.get("plx_value")
    if plx:
        kw["distance"] = (1000.0 / plx) * u.pc
    rv = row.get("rvz_radvel")
    if rv is not None:
        kw["radial_velocity"] = rv * u.km / u.s
    return SkyCoord(**kw)


def sep_arcsec(a, b):
    return float(a.separation(b).to_value(u.arcsec))


def describe(row, extra):
    """Arma el bloque de un objeto: astrometria + posiciones propagadas."""
    c0 = to_skycoord(row)
    pm_total = float(np.hypot(row["pmra"], row["pmdec"]))  # mas/yr

    positions = {}
    for label, epoch in (
        ("j2000", Time("J2000.0")),
        ("spherex_start", Time(SPHEREX_WINDOW[0])),
        ("spherex_end", Time(SPHEREX_WINDOW[1])),
    ):
        c = c0 if label == "j2000" else c0.apply_space_motion(new_obstime=epoch)
        drift = sep_arcsec(c, c0)
        positions[label] = {
            "epoch": SIMBAD_COORD_EPOCH if label == "j2000" else epoch.isot[:10],
            "ra_deg": round(float(c.ra.deg), 8),
            "dec_deg": round(float(c.dec.deg), 8),
            "drift_from_j2000_arcsec": round(drift, 2),
            "drift_from_j2000_px": round(drift / SPHEREX_PIX_ARCSEC, 2),
        }

    drift_end = positions["spherex_end"]["drift_from_j2000_arcsec"]
    block = {
        "label": extra.get("label"),
        "simbad_id": row["main_id"],
        "otype": row["otype_txt"],
        "sp_type": row["sp_type"],
        "astrometry": {
            "frame": "ICRS",
            "coord_epoch": SIMBAD_COORD_EPOCH,
            "ra_deg": round(float(row["ra"]), 8),
            "dec_deg": round(float(row["dec"]), 8),
            "coord_err_maj_mas": row["coo_err_maj"],
            "coord_err_min_mas": row["coo_err_min"],
            "coord_quality": row["coo_qual"],
            "pm_ra_cosdec_mas_yr": row["pmra"],
            "pm_dec_mas_yr": row["pmdec"],
            "pm_total_mas_yr": round(pm_total, 1),
            "pm_total_arcsec_yr": round(pm_total / 1000.0, 4),
            "pm_err_maj_mas_yr": row["pm_err_maj"],
            "pm_quality": row["pm_qual"],
            "parallax_mas": row["plx_value"],
            "parallax_err_mas": row["plx_err"],
            "distance_pc": round(1000.0 / row["plx_value"], 2) if row["plx_value"] else None,
            "radial_velocity_km_s": row["rvz_radvel"],
        },
        "sources": {
            "coordinates": row["coo_bibcode"],
            "proper_motion": row["pm_bibcode"],
            "parallax": row["plx_bibcode"],
            "simbad_update_date": row["update_date"],
            "simbad_nbref": row["nbref"],
        },
        "positions": positions,
        "pm_correction": "required" if drift_end > PM_THRESHOLD_ARCSEC else "negligible",
    }
    if "demo" in extra:
        block["demo"] = extra["demo"]
    if "note" in extra:
        block["note"] = extra["note"]
    return block


def coord_at_end(block):
    p = block["positions"]["spherex_end"]
    return SkyCoord(p["ra_deg"] * u.deg, p["dec_deg"] * u.deg, frame="icrs")


def render_yaml(targets, context):
    """YAML con una cabecera escrita a mano, para que se lea solo."""
    header = (
        "# config/targets.yaml\n"
        "#\n"
        "# Astrometria de los 4 objetivos de prueba del hackathon, mas los objetos\n"
        "# de contexto que caen en el mismo recorte.\n"
        "#\n"
        "# GENERADO: no editar a mano. Se regenera con:\n"
        "#     python core/fetch_targets.py\n"
        "#\n"
        "# Fuente de los numeros: SIMBAD (tabla basic) via TAP, mirror de Harvard.\n"
        "# Las coordenadas de SIMBAD estan en ICRS a epoca J2000.0. El movimiento\n"
        "# propio va en mas/ano, con pm_ra_cosdec ya multiplicado por cos(dec).\n"
        "#\n"
        "# POR QUE ESTE ARCHIVO EXISTE\n"
        "# Las coordenadas del enunciado son de la epoca de descubrimiento. SPHEREx\n"
        "# observa en 2025-2026. Para WISE 0855 y eps Ind B esa diferencia son ~20\n"
        "# pixeles de SPHEREx: si se apunta a las coordenadas del enunciado se mide\n"
        "# cielo vacio. Usar el bloque `positions` o propagar con core/targets.py.\n"
        "#\n"
        "# Campos por objeto:\n"
        "#   astrometry     valores crudos de SIMBAD a epoca J2000\n"
        "#   positions      posicion propagada al inicio y fin de la ventana SPHEREx\n"
        "#   pm_correction  required | negligible, segun el umbral de medio pixel\n"
        "#   sources        bibcode de cada medicion, para citar en la presentacion\n"
        "\n"
        "schema_version: 1\n"
        "generated_utc: " + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "\n"
        "generator: core/fetch_targets.py\n"
        "simbad_endpoint: " + SIMBAD_TAP + "\n"
        "reference_frame: ICRS\n"
        "coord_epoch: " + SIMBAD_COORD_EPOCH + "\n"
        "spherex_pixel_arcsec: " + str(SPHEREX_PIX_ARCSEC) + "\n"
        "spherex_window: [" + SPHEREX_WINDOW[0] + ", " + SPHEREX_WINDOW[1] + "]\n"
        "pm_correction_threshold_arcsec: " + str(PM_THRESHOLD_ARCSEC) + "\n"
        "\n"
    )

    def dump(obj):
        return yaml.dump(
            obj, allow_unicode=True, sort_keys=False,
            default_flow_style=False, width=100,
        )

    return (
        header
        + "# --- Objetivos de la demo (O5 del enunciado) ---\n"
        + dump({"targets": targets})
        + "\n# --- Objetos de contexto, no son objetivos de la demo ---\n"
        + dump({"context": context})
    )


def main():
    ap = argparse.ArgumentParser(description="Regenera config/targets.yaml desde SIMBAD.")
    ap.add_argument("--dry-run", action="store_true", help="imprime el YAML sin escribirlo")
    ap.add_argument("--out", default="config/targets.yaml")
    args = ap.parse_args()

    all_ids = [v["simbad_id"] for v in TARGETS.values()]
    all_ids += [v["simbad_id"] for v in CONTEXT.values()]
    print("Consultando SIMBAD por " + str(len(all_ids)) + " objetos...")
    rows = fetch_simbad(all_ids)

    targets = {k: describe(rows[v["simbad_id"]], v) for k, v in TARGETS.items()}
    context = {k: describe(rows[v["simbad_id"]], v) for k, v in CONTEXT.items()}

    # Desfase contra las coordenadas del enunciado.
    for key, sc in STATEMENT_COORDS.items():
        stated = SkyCoord(sc["ra"], sc["dec"], frame="icrs")
        block = targets[key]
        off = sep_arcsec(stated, coord_at_end(block))
        block["statement_coords"] = {
            "ra_sexagesimal": sc["ra"],
            "dec_sexagesimal": sc["dec"],
            "ra_deg": round(float(stated.ra.deg), 8),
            "dec_deg": round(float(stated.dec.deg), 8),
            "implied_epoch": "~2010.5, epoca WISE codificada en la designacion",
            "offset_from_spherex_end_arcsec": round(off, 1),
            "offset_from_spherex_end_px": round(off / SPHEREX_PIX_ARCSEC, 1),
            "note": "no usar estas coordenadas para apuntar; estan en positions",
        }

    # Separacion eps Ind A - B al final de la ventana (contaminacion del recorte).
    ab = sep_arcsec(coord_at_end(targets["eps_ind_b"]), coord_at_end(context["eps_ind_a"]))
    targets["eps_ind_b"]["companion_separation"] = {
        "from": "eps_ind_a",
        "arcsec": round(ab, 1),
        "px": round(ab / SPHEREX_PIX_ARCSEC, 1),
        "note": "A y B caen en pixeles distintos; Ba y Bb (0.72 arcsec) se mezclan en uno",
    }

    text = render_yaml(targets, context)
    if args.dry_run:
        print(text)
        return
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print("Escrito " + str(out) + " (" + str(len(text)) + " bytes)")


if __name__ == "__main__":
    main()
