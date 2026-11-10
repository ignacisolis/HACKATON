"""Pruebas de core/flags.py y de config/flags.yaml.

    python core/test_flags.py       # sin pytest
    pytest core/test_flags.py       # con pytest

La prueba que importa es `test_source_not_masked_for_photometry`. Enmascarar
SOURCE al medir fotometria borra el objetivo, y como SOURCE cubre ~41 % de los
pixeles, el resultado seria un espectro de cielo vacio que igual parece
plausible. La prueba fija esa distincion para que nadie la "simplifique".
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import flags as f  # noqa: E402


def test_config_loads():
    cfg = f.load_config()
    assert cfg["schema_version"] == 1
    assert cfg["extension"] == "FLAGS"
    assert cfg["source"]["doc_id"] == "SSDC-DP-017"


def test_known_bits_match_both_sources():
    """Los 23 bits de la Tabla 16 mas los 2 que solo trae el header FITS."""
    assert f.known_bits() == [
        0, 1, 2, 4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 17, 19, 20, 21, 22, 23, 24,
        25, 26, 27, 28, 29,
    ]


def test_bits_only_in_fits_header_are_marked():
    """PHANTOM y REFERENCE no estan en el documento: hay que poder distinguirlos."""
    for name in f.load_config()["only_in_fits_header"]:
        spec = f.describe(name)
        assert spec.get("origin") == "fits_header", name
        assert "NO esta en la Tabla 16" in spec["note"], name


def test_document_only_bits_are_not_in_the_fits_header():
    """Los 9 bits que el header FITS no menciona siguen viniendo del documento."""
    only_doc = f.load_config()["only_in_document"]
    assert "CROSSTALK" in only_doc and "SATELLITE_HALO" in only_doc
    for name in only_doc:
        assert f.describe(name).get("origin") != "fits_header", name


def test_documented_and_unassigned_cover_32_bits_without_overlap():
    documented = set(f.known_bits())
    unassigned = set(f.unassigned_bits())
    assert not documented & unassigned, "un bit no puede estar en las dos listas"
    assert documented | unassigned == set(range(32)), "faltan bits por clasificar"


def test_bit_21_is_source():
    """El bit que domina los recortes de la Fase 0."""
    assert f.name_of(21) == "SOURCE"
    assert f.bit_of("SOURCE") == 21


def test_names_are_unique():
    names = [f.name_of(b) for b in f.known_bits()]
    assert len(names) == len(set(names))


def test_every_bit_has_description_and_label():
    for bit in f.known_bits():
        spec = f.describe(bit)
        assert spec.get("descripcion", "").strip(), bit
        assert spec.get("label", "").strip(), bit


def test_unknown_name_raises_with_help():
    try:
        f.bit_of("NO_EXISTE")
    except KeyError as exc:
        assert "SOURCE" in str(exc), "el error deberia listar los flags validos"
    else:
        raise AssertionError("tendria que haber fallado")


def test_undocumented_bit_rejected_by_name_of():
    for bit in f.unassigned_bits():
        try:
            f.name_of(bit)
        except KeyError:
            pass
        else:
            raise AssertionError("el bit " + str(bit) + " no esta documentado")


# --------------------------------------------------------------------------
# Decodificacion
# --------------------------------------------------------------------------

def test_bitmask_and_decode_roundtrip():
    names = ["TRANSIENT", "SOURCE", "HOT"]
    value = f.bitmask(names)
    assert sorted(f.decode(value)) == sorted(names)


def test_decode_empty():
    assert f.decode(0) == []


def test_decode_surfaces_undocumented_bits():
    """Un bit sin documentar no se pierde: aparece como BIT_n."""
    value = (1 << 21) | (1 << 30)   # SOURCE + un bit sin asignar
    assert f.decode(value) == ["SOURCE", "BIT_30"]


def test_early_transient_combination():
    """TRANSIENT + SUR_ERROR significa transitorio temprano, segun el documento."""
    value = f.bitmask(["TRANSIENT", "SUR_ERROR"])
    arr = np.array([value, 0], dtype=np.uint32)
    assert f.has_all(arr, ["TRANSIENT", "SUR_ERROR"]).tolist() == [True, False]


def test_has_any_vs_has_all():
    arr = np.array([f.bitmask(["HOT"]), f.bitmask(["HOT", "COLD"])], dtype=np.uint32)
    assert f.has_any(arr, ["HOT", "COLD"]).tolist() == [True, True]
    assert f.has_all(arr, ["HOT", "COLD"]).tolist() == [False, True]


def test_works_on_2d_arrays():
    """La capa FLAGS real es 2D."""
    arr = np.zeros((4, 5), dtype=np.uint32)
    arr[1, 2] = f.bitmask(["SOURCE"])
    mask = f.has_any(arr, ["SOURCE"])
    assert mask.shape == (4, 5)
    assert mask.sum() == 1 and mask[1, 2]


# --------------------------------------------------------------------------
# Mascaras: la parte que importa
# --------------------------------------------------------------------------

def test_source_not_masked_for_photometry():
    """SOURCE se enmascara para el fondo, NUNCA para fotometria."""
    assert "SOURCE" in f.mask_flags("background")
    assert "SOURCE" not in f.mask_flags("photometry"), (
        "Enmascarar SOURCE en fotometria borra el objetivo: SOURCE marca los "
        "pixeles de la fuente que se quiere medir, y cubre ~41 % del recorte."
    )


def test_photometry_mask_keeps_the_target_pixel():
    """Prueba de extremo a extremo del error que se quiere evitar."""
    imagen = np.zeros((3, 3), dtype=float)
    imagen[1, 1] = 100.0                      # el objetivo
    capa = np.zeros((3, 3), dtype=np.uint32)
    capa[1, 1] = f.bitmask(["SOURCE"])        # marcado como fuente conocida

    usables = f.good_pixels(capa, "photometry")
    assert imagen[usables].sum() == 100.0, "la fotometria perdio el objetivo"

    # Y para el fondo pasa lo contrario, que es lo correcto.
    fondo = f.good_pixels(capa, "background")
    assert imagen[fondo].sum() == 0.0, "el fondo incluyo la fuente"


def test_background_mask_is_a_superset_of_photometry():
    """Todo lo que se enmascara para fotometria se enmascara para el fondo."""
    photo = set(f.mask_flags("photometry"))
    bg = set(f.mask_flags("background"))
    assert photo <= bg, photo - bg


def test_the_difference_between_masks_is_what_we_documented():
    diff = set(f.mask_flags("background")) - set(f.mask_flags("photometry"))
    assert diff == {"SOURCE", "TRANSIENT", "OVERFLOW", "OUTLIER"}


def test_mask_flags_names_all_exist():
    for purpose in f.mask_sets():
        for name in f.mask_flags(purpose):
            f.bit_of(name)   # levanta KeyError si hay un nombre mal escrito


def test_mask_for_requires_explicit_purpose():
    try:
        f.mask_flags("todo")
    except KeyError as exc:
        assert "photometry" in str(exc)
    else:
        raise AssertionError("un proposito inventado deberia fallar")


def test_unusable_pixels_are_masked_everywhere():
    """Lo que el documento llama inservible no sobrevive en ninguna mascara."""
    for name in ("NONFUNC", "HOT", "COLD"):
        assert name in f.mask_flags("photometry"), name
        assert name in f.mask_flags("background"), name


def test_fullsample_is_not_masked():
    """FULLSAMPLE es informativo: enmascararlo tiraria dato bueno."""
    assert "FULLSAMPLE" not in f.mask_flags("photometry")
    assert "FULLSAMPLE" not in f.mask_flags("background")
    assert "CUIDADO" in f.describe("FULLSAMPLE")["note"]


# --------------------------------------------------------------------------
# Resumen para metadata
# --------------------------------------------------------------------------

def test_bit_counts_reproduces_fase0_observation():
    """Una capa con 41 % de SOURCE se reporta como tal."""
    rng = np.random.default_rng(0)
    capa = np.where(rng.random((100, 100)) < 0.41, f.bitmask(["SOURCE"]), 0)
    capa = capa.astype(np.uint32)
    rows = f.bit_counts(capa)
    assert rows[0]["name"] == "SOURCE"
    assert 0.38 < rows[0]["fraction"] < 0.44


def test_bit_counts_skips_absent_flags():
    capa = np.zeros((10, 10), dtype=np.uint32)
    assert f.bit_counts(capa) == []
    assert len(f.bit_counts(capa, include_zero=True)) == len(f.known_bits())


def test_undocumented_bits_present_is_an_alarm():
    capa = np.zeros((10, 10), dtype=np.uint32)
    assert f.undocumented_bits_present(capa) == []
    capa[0, 0] = 1 << 30
    found = f.undocumented_bits_present(capa)
    assert len(found) == 1 and found[0]["bit"] == 30


def test_source_doc_is_citable():
    src = f.source_doc()
    for field in ("document", "doc_id", "version", "date", "url", "table"):
        assert str(src.get(field, "")).strip(), field


# --------------------------------------------------------------------------
# Segunda fuente: el header del FITS
# --------------------------------------------------------------------------

# Tarjetas copiadas de un cutout real de SPHEREx (release l2b-v20-2025-251,
# detector D2, exposicion 2025-06-08). Fijarlas aca hace la prueba
# determinista y sin red; cross_check_fits() contra datos frescos se corre a
# mano cuando sale un release nuevo.
REAL_FLAGS_HEADER = {
    "EXTTYPE": "MASK",
    "L2 N_OUTLIER": 98707,
    "L2 N_TRANSIENT": 19834,
    "L2 N_OVERFLOW": 504,
    "L2 N_SUR_ERROR": 12158,
    "L2 N_NONFUNC": 1789,
    "L2 N_FULLSAMPLE": 240,
    "MP_TRANSIENT": 0,
    "MP_OVERFLOW": 1,
    "MP_SUR_ERROR": 2,
    "MP_PHANTOM": 4,
    "MP_REFERENCE": 5,
    "MP_NONFUNC": 6,
    "MP_DICHROIC": 7,
    "MP_MISSING_DATA": 9,
    "MP_HOT": 10,
    "MP_COLD": 11,
    "MP_FULLSAMPLE": 12,
    "MP_PHANMISS": 14,
    "MP_NONLINEAR": 15,
    "MP_PERSIST": 17,
    "MP_OUTLIER": 19,
    "MP_SOURCE": 21,
    "EXTNAME": "FLAGS",
    "NAXIS1": 29,
}


def test_from_fits_header_reads_mp_keywords():
    bits = f.from_fits_header(REAL_FLAGS_HEADER)
    assert bits["SOURCE"] == 21
    assert bits["TRANSIENT"] == 0
    assert len(bits) == 16, "el header real trae 16 tarjetas MP_"
    assert "EXTNAME" not in bits and "NAXIS1" not in bits


def test_from_fits_header_ignores_junk():
    assert f.from_fits_header({"MP_RARO": "no es un numero"}) == {}
    assert f.from_fits_header({}) == {}


def test_cross_check_against_real_header_agrees():
    """Las dos fuentes coinciden en los bits que comparten."""
    r = f.cross_check_fits(REAL_FLAGS_HEADER)
    assert r["mismatched"] == {}, "un bit significa cosas distintas en cada fuente"
    assert r["only_in_fits"] == {}, "el header trae bits que el YAML no conoce"
    assert r["ok"]
    assert len(r["agree"]) == 16


def test_cross_check_lists_the_nine_document_only_bits():
    r = f.cross_check_fits(REAL_FLAGS_HEADER)
    assert set(r["only_in_config"]) == set(f.load_config()["only_in_document"])
    assert len(r["only_in_config"]) == 9


def test_cross_check_detects_a_renumbered_bit():
    """Si un release mueve un bit, la comprobacion tiene que gritar."""
    header = dict(REAL_FLAGS_HEADER, MP_SOURCE=30)
    r = f.cross_check_fits(header)
    assert not r["ok"]
    assert r["mismatched"]["SOURCE"] == {"fits": 30, "config": 21}


def test_cross_check_detects_a_new_bit():
    header = dict(REAL_FLAGS_HEADER, MP_FLAMANTE=31)
    r = f.cross_check_fits(header)
    assert not r["ok"]
    assert r["only_in_fits"] == {"FLAMANTE": 31}


def test_pipeline_counts_are_full_frame_not_cutout():
    """La trampa: las cuentas del header son de la imagen entera."""
    counts = f.pipeline_counts(REAL_FLAGS_HEADER)
    assert counts["OUTLIER"] == 98707
    assert "EXTNAME" not in counts
    cutout_pixels = REAL_FLAGS_HEADER["NAXIS1"] ** 2
    assert counts["OUTLIER"] > cutout_pixels, (
        "si esto fallara, las cuentas serian del recorte y podriamos usarlas tal cual"
    )
    assert "CUIDADO" in f.load_config()["fits_header_extras"]["L2 N_<NOMBRE>"]


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
