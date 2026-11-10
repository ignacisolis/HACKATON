"""Genera contracts/fixtures/*.json a partir de datos REALES.

Los fixtures son respuestas de ejemplo para que Bruno arme el frontend sin
esperar al backend. La diferencia con inventarlos a mano es que estos usan las
fechas, detectores, longitudes de onda y cuentas de flags medidas de verdad
contra IRSA y contra un cutout real, asi que el frontend se encuentra con los
casos raros desde el dia uno y no en la semana de la presentacion.

Dos juegos, a proposito los dos extremos:
  r_dra      el caso rico:  2483 cuadros, 222 fechas, ~34 epocas por banda
  wise_0855  el caso pobre:  256 cuadros,  27 fechas,  ~3 epocas por banda

Uso:
    python contracts/make_fixtures.py

Los flujos son inventados y estan marcados como tales: medirlos de verdad es la
tarea 23. Todo lo demas es real.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import yaml
from astropy.time import Time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import targets as tg  # noqa: E402

OUT = Path(__file__).resolve().parent / "fixtures"
COVERAGE = Path(__file__).resolve().parent.parent / "config" / "coverage.yaml"

# Cuentas de flags de un cutout real de 29x29 de R Dra, release
# l2b-v20-2025-251. SOURCE al 100 % no es un error: el recorte cae entero dentro
# de una mascara de fuentes.
REAL_CUTOUT_FLAGS = [
    {"bit": 21, "name": "SOURCE", "label": "Known source", "pixels": 841, "fraction": 1.0},
    {"bit": 2, "name": "SUR_ERROR", "label": "SUR data handling error", "pixels": 50, "fraction": 0.059},
    {"bit": 0, "name": "TRANSIENT", "label": "Transient (cosmic ray)", "pixels": 48, "fraction": 0.057},
    {"bit": 1, "name": "OVERFLOW", "label": "Overflow (half-well reached)", "pixels": 16, "fraction": 0.019},
    {"bit": 17, "name": "PERSIST", "label": "Persistence", "pixels": 1, "fraction": 0.001},
]
REAL_FULL_FRAME_FLAGS = {
    "OUTLIER": 98707, "TRANSIENT": 19834, "SUR_ERROR": 12158,
    "NONFUNC": 1789, "OVERFLOW": 504, "FULLSAMPLE": 240,
}
REAL_RELEASE = "l2b-v20-2025-251"


def band_of(wavelength_um, lo=0.75, hi=5.01, n=102):
    """Numero de banda 1..102 por longitud de onda. Convencion a confirmar."""
    frac = (wavelength_um - lo) / (hi - lo)
    return int(np.clip(round(frac * (n - 1)) + 1, 1, n))


def frames_fixture(key, cov, max_frames=40):
    """Cuadros de ejemplo, repartidos entre las fechas y detectores reales."""
    c = cov[key]
    rng = np.random.default_rng(42)
    dates = c["dates"]
    dets = {d: v for d, v in c["detectors"].items()}

    frames = []
    for i, det_name in enumerate(sorted(dets) * 10):
        if len(frames) >= max_frames:
            break
        d = dets[det_name]
        if d["wavelength_min_um"] is None:
            continue
        date = dates[i % len(dates)]
        mjd = float(Time(date).mjd) + 0.5
        lam = float(rng.uniform(d["wavelength_min_um"], d["wavelength_max_um"]))
        bw = lam / d["resolving_power"]
        short = det_name.replace("SPHEREx-", "")
        frames.append({
            "id": REAL_RELEASE + "/level2_" + date.replace("-", "") + "_1" + short,
            "mjd": round(mjd, 6),
            "date": Time(mjd, format="mjd").isot,
            "detector": short,
            "wavelength_um": round(lam, 4),
            "bandwidth_um": round(bw, 4),
            "band": band_of(lam),
            "release": REAL_RELEASE,
            "image_url": "/api/frame/" + str(len(frames)) + "/png?stretch=asinh",
            "target_xy": [29.5, 29.5],
            "flagged_fraction": round(float(rng.uniform(0.1, 1.0)), 3),
            "quality": "ok",
        })
    frames.sort(key=lambda f: f["mjd"])

    ra, dec = tg.target_position(key, "2026-05-14")
    return {
        "_fixture_note": ("Fechas, detectores y longitudes de onda REALES, medidos "
                          "contra IRSA. Los flujos y flagged_fraction son inventados."),
        "query": {
            "ra": round(ra, 5), "dec": round(dec, 5), "size": 0.1, "target": key,
            "resolved_from": "targets.yaml + movimiento propio",
            "coord_epoch_applied": "2026-05-14",
        },
        "n_frames": c["observations"],
        "n_dates": c["distinct_dates"],
        "_frames_in_this_fixture": len(frames),
        "frames": frames,
    }


def spectrum_fixture(key, cov):
    """Espectro de ejemplo con las 102 bandas repartidas en los 6 detectores."""
    c = cov[key]
    rng = np.random.default_rng(7)
    points = []
    for det_name, d in sorted(c["detectors"].items()):
        if d["wavelength_min_um"] is None:
            continue
        short = det_name.replace("SPHEREx-", "")
        for lam in np.linspace(d["wavelength_min_um"], d["wavelength_max_um"], 17):
            bw = float(lam) / d["resolving_power"]
            flux = float(rng.uniform(0.1, 0.9))
            points.append({
                "wavelength_um": round(float(lam), 4),
                "bandwidth_um": round(bw, 4),
                "band": band_of(float(lam)),
                "flux": round(flux, 4),
                "flux_err": round(flux * 0.06, 4),
                "unit": "MJy/sr",
                "detector": short,
                "n_epochs": int(round(d["obs_per_channel_est"])),
                "flagged_fraction": round(float(rng.uniform(0.0, 0.3)), 3),
                "quality": "ok",
            })
    points.sort(key=lambda p: p["wavelength_um"])
    ra, dec = tg.target_position(key, "2026-05-14")
    return {
        "_fixture_note": ("Longitudes de onda, anchos de banda y n_epochs REALES. "
                          "Los flujos son inventados: medirlos es la tarea 23."),
        "query": {"ra": round(ra, 5), "dec": round(dec, 5), "target": key},
        "aperture_px": 2.5,
        "mask_purpose": "photometry",
        "n_points": len(points),
        "n_epochs_used": c["observations"],
        "points": points,
    }


def frame_meta_fixture():
    """Metadata de un cuadro, con los flags de un cutout real."""
    return {
        "_fixture_note": "Header y cuentas de flags de un cutout REAL de R Dra.",
        "id": REAL_RELEASE + "/level2_2025W23_2B_0696_1D2",
        "mjd": 60834.788416907,
        "date": "2025-06-08T18:55:19.221",
        "detector": "D2",
        "release": REAL_RELEASE,
        "exposure_s": 113.5826,
        "wavelength_um": 1.5143,
        "bandwidth_um": 0.0366,
        "wcs": {"crval": [247.081972417, 66.890441488],
                "ctype": ["RA---TAN-SIP", "DEC--TAN-SIP"]},
        "flags": {
            "extension_is_mask": True,
            "cutout_counts": REAL_CUTOUT_FLAGS,
            "full_frame_counts": REAL_FULL_FRAME_FLAGS,
            "undocumented_bits_present": [],
        },
        "mask_layers": [r["name"] for r in REAL_CUTOUT_FLAGS],
    }


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    if not COVERAGE.is_file():
        raise SystemExit("Falta " + str(COVERAGE) + ": corre core/fetch_coverage.py")
    cov = yaml.safe_load(COVERAGE.read_text(encoding="utf-8"))["coverage"]
    OUT.mkdir(parents=True, exist_ok=True)

    files = {
        "frames.json": frames_fixture("r_dra", cov),
        "frames-sparse.json": frames_fixture("wise_0855", cov),
        "spectrum.json": spectrum_fixture("r_dra", cov),
        "frame-meta.json": frame_meta_fixture(),
    }
    for name, payload in files.items():
        p = OUT / name
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
        print("escrito " + str(p.relative_to(OUT.parent.parent)) + " ("
              + str(p.stat().st_size) + " bytes)")


if __name__ == "__main__":
    main()
