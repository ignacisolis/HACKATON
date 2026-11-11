"""Pruebas de core/targets.py y de config/targets.yaml.

Corre sin pytest:
    python core/test_targets.py
O con pytest si esta instalado:
    pytest core/test_targets.py

La prueba que importa es `test_wise0855_epoch_is_j2000`. Todo el resto del
proyecto depende de una suposicion: que las coordenadas de SIMBAD estan a
epoca J2000.0. Si eso fuera falso, apuntariamos mal por decenas de pixeles y
no lo notariamos, porque el campo igual se veria lleno de estrellas.

La prueba la verifica sin creernos nada: propaga la posicion J2000 de SIMBAD
hasta 2010.5 y compara con las coordenadas que el propio nombre del objeto
lleva codificadas, 'WISE J085510.83-071442.5', que son de la epoca WISE. Si
coinciden dentro de un arcsec, la suposicion es correcta.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import targets as t  # noqa: E402

# Coordenadas que el enunciado del hackathon da para WISE 0855. Son las de la
# designacion WISE, o sea la posicion en la epoca de descubrimiento.
STATEMENT_RA_DEG = 133.79512917
STATEMENT_DEC_DEG = -7.24514722
WISE_EPOCH = "2010-07-01"  # ~2010.5, mitad de la campania criogenica de WISE


def test_config_loads():
    cfg = t.load_config()
    assert cfg["schema_version"] == 1
    assert cfg["coord_epoch"] == "J2000.0"
    assert set(t.target_keys()) == {"eps_ind_b", "wise_0855", "rw_aur", "r_dra"}


def test_every_target_has_sources():
    """Sin bibcode no podemos citar el dato en la presentacion."""
    for key in t.target_keys():
        src = t.get_target(key)["sources"]
        assert src["coordinates"], key
        assert src["proper_motion"], key
        assert src["parallax"], key


def test_wise0855_epoch_is_j2000():
    """La prueba central: confirma la epoca de las coordenadas de SIMBAD."""
    ra, dec = t.target_position("wise_0855", WISE_EPOCH)
    off = t.separation_arcsec(ra, dec, STATEMENT_RA_DEG, STATEMENT_DEC_DEG)
    # 8.15 arcsec/ano: un ano de error de epoca daria 8 arcsec de desfase.
    # Quedar debajo de 1 arcsec solo es posible si la epoca de partida es J2000.
    assert off < 1.0, (
        "Propagando desde J2000 hasta " + WISE_EPOCH + " el desfase contra la "
        "designacion WISE es " + format(off, ".2f") + " arcsec. Se esperaba < 1. "
        "La epoca de las coordenadas de SIMBAD no es la que creemos."
    )


def test_statement_coords_are_not_usable_today():
    """Las coordenadas del enunciado apuntan a cielo vacio en la era SPHEREx."""
    blk = t.get_target("wise_0855")
    off_px = blk["statement_coords"]["offset_from_spherex_end_px"]
    assert off_px > 3, (
        "Si el desfase fuera menor a unos pixeles, la correccion de movimiento "
        "propio no haria falta y sobraria media tarea 21."
    )
    # La fecha sale de la configuracion, no hardcodeada: la ventana del archivo
    # cambia cuando IRSA publica mas datos.
    window_end = t.load_config()["spherex_window"][1]
    ra, dec = t.target_position("wise_0855", str(window_end))
    recomputed = t.separation_px(ra, dec, STATEMENT_RA_DEG, STATEMENT_DEC_DEG)
    assert abs(recomputed - off_px) < 0.2, "El YAML y el calculo en vivo no coinciden"


def test_high_pm_targets_flagged():
    """Los dos objetivos cercanos necesitan correccion; los lejanos no."""
    assert t.needs_pm_correction("wise_0855")
    assert t.needs_pm_correction("eps_ind_b")
    assert not t.needs_pm_correction("rw_aur")
    assert not t.needs_pm_correction("r_dra")


def test_drift_matches_yaml():
    """Propagar en vivo reproduce las posiciones guardadas en el YAML."""
    cfg = t.load_config()
    start, end = cfg["spherex_window"]
    for key in t.target_keys():
        blk = t.get_target(key)
        for label, when in (("spherex_start", start), ("spherex_end", end)):
            ra, dec = t.target_position(key, str(when))
            saved = blk["positions"][label]
            off = t.separation_arcsec(ra, dec, saved["ra_deg"], saved["dec_deg"])
            assert off < 0.05, (key, label, off)


def test_eps_ind_pair_is_resolved_from_the_star():
    """eps Ind B cae en otro pixel que eps Ind A: se puede medir sin la estrella."""
    sep = t.get_target("eps_ind_b")["companion_separation"]
    assert sep["px"] > 10, "Si A y B compartieran pixel, la fotometria de B seria imposible"


def test_propagate_is_pure_and_vectorizable():
    """propagate() no depende de la configuracion y acepta valores sueltos."""
    ra, dec = t.propagate(10.0, 20.0, 1000.0, 0.0, to_epoch="2001-01-01",
                          from_epoch="2000-01-01")
    # 1000 mas/ano en RA durante un ano = 1 arcsec sobre el cielo.
    moved = t.separation_arcsec(ra, dec, 10.0, 20.0)
    assert 0.95 < moved < 1.05, moved


def test_zero_pm_does_not_move():
    ra, dec = t.propagate(10.0, 20.0, 0.0, 0.0, to_epoch="2026-01-01")
    assert t.separation_arcsec(ra, dec, 10.0, 20.0) < 1e-6


def test_mjd_input_accepted():
    """Los headers FITS traen MJD, no texto."""
    by_mjd = t.target_position("wise_0855", 60800.0)        # 2025-05-05
    by_iso = t.target_position("wise_0855", "2025-05-05")
    assert t.separation_arcsec(*by_mjd, *by_iso) < 0.05


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in tests:
        try:
            fn()
            print("  ok    " + fn.__name__)
        except AssertionError as exc:
            failed += 1
            print("  FALLA " + fn.__name__ + ": " + str(exc))
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print("  ERROR " + fn.__name__ + ": " + type(exc).__name__ + ": " + str(exc))
    print("\n" + str(len(tests) - failed) + "/" + str(len(tests)) + " pruebas pasaron")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
