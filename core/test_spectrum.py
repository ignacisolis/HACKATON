"""Pruebas de core/spectrum.py y core/bands.py. Tarea 23.

    python core/test_spectrum.py
    pytest core/test_spectrum.py

El "Listo cuando" de la tarea pide probar con WISE 0855 REAL, no sintetico. Eso
no puede correr en CI, porque necesita red y bajar ~90 MB de recortes. Esta
suite cubre la aritmetica y las reglas; la verificacion con datos reales se corre
a mano con `python core/check_real_spectrum.py` y su resultado esta en
docs/ciencia.md seccion 7.

Lo que si entra aca es la grilla de bandas contra una medicion real: las 6
exposiciones consecutivas de D2 sobre R Dra caen en las bandas 28 a 33, y eso
queda fijado como prueba.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from astropy.wcs import WCS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import bands as bd  # noqa: E402
from core import flags as fl  # noqa: E402
from core import spectrum as sp  # noqa: E402
from core.datatypes import Frame, SpectrumPoint  # noqa: E402

PIX_ARCSEC = 6.2
PIX_DEG = PIX_ARCSEC / 3600.0
OMEGA_SR = (PIX_DEG * math.pi / 180.0) ** 2      # angulo solido de un pixel
ESCALA = OMEGA_SR * 1e6                           # MJy/sr -> Jy por pixel


def make_wcs(ra=133.76, dec=-7.24, ref_at=(14.0, 14.0)):
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [ref_at[0] + 1, ref_at[1] + 1]
    w.wcs.cdelt = [-PIX_DEG, PIX_DEG]
    return w


def make_frame(img, mjd=61000.0, detector="D2", lam=1.4017, bw=0.0336,
               var=1.0, flag_bits=(), ref_at=(14.0, 14.0)):
    n = img.shape[0]
    flags = np.zeros((n, n), dtype=np.uint32)
    if flag_bits:
        flags[:, :] = fl.bitmask(list(flag_bits))
    return Frame(image=img, flags=flags, variance=np.full((n, n), var),
                 wcs=make_wcs(ref_at=ref_at), mjd=mjd, detector=detector,
                 wavelength_um=lam, bandwidth_um=bw)


def frame_un_pixel(valor=100.0, **kw):
    """Todo cero menos un pixel en el objetivo. Hace la cuenta exacta."""
    img = np.zeros((29, 29))
    img[14, 14] = valor
    return make_frame(img, **kw)


# --------------------------------------------------------------------------
# core.bands
# --------------------------------------------------------------------------

def test_hay_102_bandas():
    assert bd.n_bands() == 102
    assert len(bd.all_bands()) == 102


def test_seis_detectores_de_17_canales():
    res = bd.summary()
    assert len(res) == 6
    for d in res:
        assert d["n"] == 17, d


def test_las_bandas_cubren_el_rango_de_la_mision():
    todas = bd.all_bands()
    assert todas[0]["wavelength_min_um"] < 0.75
    assert todas[-1]["wavelength_max_um"] > 5.0


def test_las_bandas_estan_ordenadas_y_sin_huecos_dentro_del_detector():
    por_det = {}
    for b in bd.all_bands():
        por_det.setdefault(b["detector"], []).append(b)
    for det, lista in por_det.items():
        for a, b in zip(lista, lista[1:]):
            assert b["band"] == a["band"] + 1, det
            # El borde superior de una es el inferior de la siguiente.
            assert abs(b["wavelength_min_um"] - a["wavelength_max_um"]) < 1e-4, det


def test_el_espaciado_es_logaritmico_a_r_constante():
    """Si fuera lineal, lambda/ancho cambiaria a lo largo del detector."""
    for det in ("D1", "D2", "D4", "D6"):
        rs = [b["wavelength_um"] / b["bandwidth_um"]
              for b in bd.all_bands() if b["detector"] == det]
        assert max(rs) - min(rs) < 0.5, (det, min(rs), max(rs))


def test_el_ancho_de_banda_crece_con_la_longitud_de_onda():
    anchos = [b["bandwidth_um"] for b in bd.all_bands() if b["detector"] == "D2"]
    assert all(b > a for a, b in zip(anchos, anchos[1:]))


# Longitudes de onda MEDIDAS en 6 exposiciones consecutivas reales de D2 sobre
# R Dra, release l2b-v20-2025-251.
LAMBDAS_REALES_D2 = [1.4017, 1.4359, 1.4706, 1.5067, 1.5431, 1.5806]


def test_las_exposiciones_reales_caen_en_bandas_consecutivas():
    """Valida la grilla contra el instrumento, no contra si misma.

    Si la grilla estuviera mal espaciada, seis exposiciones que avanzan un canal
    cada una no caerian en seis bandas seguidas.
    """
    asignadas = [bd.band_of_wavelength(lam) for lam in LAMBDAS_REALES_D2]
    assert asignadas == [28, 29, 30, 31, 32, 33], asignadas
    for b in asignadas:
        assert bd.band_info(b)["detector"] == "D2"


def test_band_of_wavelength_fuera_de_rango():
    assert bd.band_of_wavelength(0.4) is None
    assert bd.band_of_wavelength(12.0) is None


def test_band_of_wavelength_en_el_centro_de_cada_banda():
    """Con el detector es exacto para las 102, solapes incluidos."""
    for b in bd.all_bands():
        got = bd.band_of_wavelength(b["wavelength_um"], b["detector"])
        assert got == b["band"], (b["band"], got)


def test_las_bandas_se_solapan_en_las_costuras():
    """Los detectores se solapan, asi que lambda sola no determina la banda.

    Hay 5 costuras entre detectores pero SEIS pares de bandas solapadas: en la
    costura D4/D5 el poder resolvente salta de 34.9 a 111.6, asi que las bandas
    de D4 son unas 3 veces mas anchas y la ultima de D4 alcanza a cubrir DOS
    bandas de D5. Es consecuencia directa del salto de R.
    """
    solapes = bd.overlapping_bands()
    assert len(solapes) == 6, [s["bands"] for s in solapes]
    # El par extra es el de D4/D5.
    d4d5 = [s for s in solapes if s["detectors"] == ("D4", "D5")]
    assert len(d4d5) == 2, d4d5
    for s in solapes:
        assert s["overlap_um"] > 0
        assert s["detectors"][0] != s["detectors"][1]
        # La misma lambda cae en las dos bandas si se pasa cada detector.
        medio = (s["overlap_min_um"] + s["overlap_max_um"]) / 2
        a = bd.band_of_wavelength(medio, s["detectors"][0])
        b = bd.band_of_wavelength(medio, s["detectors"][1])
        assert a == s["bands"][0] and b == s["bands"][1], (medio, a, b, s)


def test_band_of_wavelength_sin_detector_es_determinista():
    """Sin detector devuelve la banda mas chica, y esta documentado."""
    s = bd.overlapping_bands()[0]
    medio = (s["overlap_min_um"] + s["overlap_max_um"]) / 2
    assert bd.band_of_wavelength(medio) == min(s["bands"])


def test_band_of_wavelength_detector_desconocido_falla():
    try:
        bd.band_of_wavelength(1.4, "D9")
    except KeyError as exc:
        assert "D9" in str(exc)
    else:
        raise AssertionError("un detector inexistente tendria que fallar")


def test_bands_of_detector():
    assert bd.bands_of_detector("D2") == list(range(18, 35))
    assert bd.bands_of_detector("SPHEREx-D1") == list(range(1, 18))


def test_band_info_fuera_de_rango_falla():
    for mal in (0, 103):
        try:
            bd.band_info(mal)
        except KeyError:
            pass
        else:
            raise AssertionError("la banda " + str(mal) + " no existe")


# --------------------------------------------------------------------------
# extract
# --------------------------------------------------------------------------

def test_extract_recupera_el_flujo_con_las_unidades_bien():
    """Un pixel de valor conocido tiene que dar un flujo calculable a mano."""
    f = frame_un_pixel(valor=100.0)
    (p,) = sp.extract([f], ra=133.76, dec=-7.24)
    assert p.unit == "Jy"
    esperado = 100.0 * ESCALA
    assert abs(p.flux - esperado) / esperado < 1e-6, (p.flux, esperado)


def test_extract_asigna_la_banda():
    f = frame_un_pixel(lam=1.4017)
    (p,) = sp.extract([f], ra=133.76, dec=-7.24)
    assert p.band == 28 and p.detector == "D2"


def test_extract_resta_el_fondo():
    img = np.full((29, 29), 5.0)
    img[14, 14] = 105.0
    f = make_frame(img)
    (p,) = sp.extract([f], ra=133.76, dec=-7.24)
    # El fondo de 5.0 se resta de cada pixel de la apertura.
    n = p.n_pixels
    esperado = (105.0 - 5.0 + (n - 1) * 0.0) * ESCALA
    assert abs(p.flux - esperado) / esperado < 1e-6, (p.flux, esperado, n)
    assert abs(p.background - 5.0) < 1e-9


def test_sin_anillo_limpio_no_inventa_un_fondo_cero():
    """Lo que paso de verdad con R Dra: todo el recorte era SOURCE."""
    f = frame_un_pixel(valor=100.0, flag_bits=("SOURCE",))
    (p,) = sp.extract([f], ra=133.76, dec=-7.24)
    assert p.background is None, "no deberia haber estimado fondo"
    assert p.quality == "suspect", "y tiene que decir que el punto es dudoso"
    # Pero el flujo igual se mide: SOURCE no se enmascara para fotometria.
    assert p.flux > 0


def test_source_no_se_enmascara_para_fotometria():
    con = frame_un_pixel(valor=100.0, flag_bits=("SOURCE",))
    (p,) = sp.extract([con], ra=133.76, dec=-7.24)
    assert p.n_pixels > 0 and p.flux > 0
    # Con la mascara de fondo, en cambio, no queda nada que medir.
    assert sp.extract([con], ra=133.76, dec=-7.24, mask_purpose="background") == []


def test_los_pixeles_malos_se_descartan_y_se_reportan():
    img = np.full((29, 29), 10.0)
    f = make_frame(img)
    f.flags = f.flags.copy()
    f.flags[13:16, 13:16] = fl.bitmask(["HOT"])   # 9 px malos en la apertura
    (p,) = sp.extract([f], ra=133.76, dec=-7.24)
    assert p.flagged_fraction > 0.3, p.flagged_fraction
    assert p.n_pixels > 0


def test_extract_exige_objetivo():
    try:
        sp.extract([frame_un_pixel()])
    except ValueError as exc:
        assert "target_key" in str(exc)
    else:
        raise AssertionError("tendria que exigir objetivo")


def test_extract_ordena_por_longitud_de_onda():
    fs = [frame_un_pixel(lam=lam) for lam in (1.58, 1.40, 1.47)]
    puntos = sp.extract(fs, ra=133.76, dec=-7.24)
    assert [round(p.wavelength_um, 2) for p in puntos] == [1.40, 1.47, 1.58]


def test_extract_usa_el_movimiento_propio_del_objetivo():
    """Con target_key la apertura sigue al objeto, no a una posicion fija."""
    import core.targets as tg
    ra0, dec0 = tg.target_position("wise_0855", 61000.0)
    img = np.zeros((29, 29))
    img[14, 14] = 100.0
    f = Frame(image=img, flags=np.zeros((29, 29), np.uint32),
              variance=np.ones((29, 29)), wcs=make_wcs(ra0, dec0),
              mjd=61000.0, detector="D2", wavelength_um=1.4017, bandwidth_um=0.0336)
    (p,) = sp.extract([f], target_key="wise_0855")
    assert p.flux > 0, "no encontro el objetivo en su posicion propagada"


def test_extract_salta_cuadros_sin_wcs():
    f = frame_un_pixel()
    f.wcs = None
    assert sp.extract([f], ra=133.76, dec=-7.24) == []


# --------------------------------------------------------------------------
# combine: la consideracion C8
# --------------------------------------------------------------------------

def punto(lam=1.4017, flujo=1.0, err=0.1, mjd=61000.0, det="D2"):
    return SpectrumPoint(wavelength_um=lam, bandwidth_um=0.0336, flux=flujo,
                         flux_err=err, mjd=mjd, detector=det, n_pixels=20,
                         flagged_fraction=0.0,
                         band=bd.band_of_wavelength(lam, det))


def test_combine_agrupa_por_banda():
    puntos = [punto(lam=1.4017), punto(lam=1.4100), punto(lam=1.4706)]
    res = sp.combine(puntos)
    # 1.4017 y 1.4100 caen en la banda 28; 1.4706 en la 30.
    assert [p.band for p in res] == [28, 30], [p.band for p in res]
    assert res[0].n_epochs == 2 and res[1].n_epochs == 1


def test_combine_mejora_la_senal_ruido_como_raiz_de_n():
    """Es el numero concreto detras de la consideracion C8."""
    puntos = [punto(flujo=1.0, err=0.1, mjd=61000.0 + k) for k in range(4)]
    (res,) = sp.combine(puntos)
    assert abs(res.flux - 1.0) < 1e-9
    assert abs(res.flux_err - 0.1 / 2.0) < 1e-9, res.flux_err   # sqrt(4) = 2
    assert res.n_epochs == 4


def test_combine_pondera_por_inversa_de_la_varianza():
    """Una medida mala no debe arrastrar el promedio."""
    puntos = [punto(flujo=1.0, err=0.1), punto(flujo=5.0, err=10.0, mjd=61001.0)]
    (res,) = sp.combine(puntos)
    assert abs(res.flux - 1.0) < 0.01, res.flux


def test_combine_usa_el_centro_de_la_banda_no_el_promedio():
    puntos = [punto(lam=1.4017), punto(lam=1.4100, mjd=61001.0)]
    (res,) = sp.combine(puntos)
    assert abs(res.wavelength_um - bd.band_info(28)["wavelength_um"]) < 1e-9


def test_combine_descarta_lo_que_cae_fuera_de_la_grilla():
    p = punto()
    p.wavelength_um = 0.3
    p.band = None
    assert sp.combine([p]) == []


def test_combine_sin_puntos():
    assert sp.combine([]) == []


def test_snr_gain_reporta_la_mejora():
    puntos = [punto(mjd=61000.0 + k) for k in range(9)]
    res = sp.snr_gain(sp.combine(puntos))
    assert len(res) == 1
    assert res[0]["n_epochs"] == 9
    assert abs(res[0]["expected_gain"] - 3.0) < 1e-9


# --------------------------------------------------------------------------
# light_curve
# --------------------------------------------------------------------------

def test_light_curve_exige_banda_o_detector():
    """Mezclar longitudes de onda hace que un objeto rojo parezca variar."""
    try:
        sp.light_curve([punto()])
    except ValueError as exc:
        assert "band" in str(exc) and "rojo" in str(exc)
    else:
        raise AssertionError("tendria que exigir band o detector")


def test_light_curve_filtra_por_banda_y_ordena_por_fecha():
    puntos = [punto(lam=1.4017, flujo=2.0, mjd=61010.0),
              punto(lam=1.4017, flujo=1.0, mjd=61000.0),
              punto(lam=1.4706, flujo=9.0, mjd=61005.0)]
    mjds, flujos, errs = sp.light_curve(puntos, band=28)
    assert mjds.tolist() == [61000.0, 61010.0]
    assert flujos.tolist() == [1.0, 2.0]


def test_light_curve_filtra_por_detector():
    puntos = [punto(det="D2", lam=1.4017), punto(det="D5", lam=4.0, mjd=61001.0)]
    mjds, flujos, errs = sp.light_curve(puntos, detector="D2")
    assert len(mjds) == 1


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
