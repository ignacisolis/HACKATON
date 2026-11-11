"""Pruebas de core/subtract.py. Tarea 22.

    python core/test_subtract.py       # sin pytest
    pytest core/test_subtract.py       # con pytest

Las dos pruebas que cierran la tarea son las dos mitades de su "Listo cuando":

  test_se_niega_a_restar_lo_que_no_es_comparable
      "core.subtract() solo acepta mismo detector y lambda parecida"

  test_el_movimiento_de_wise0855_se_ve_en_la_resta
      "el movimiento de WISE 0855 se ve"

La segunda usa cuadros SINTETICOS, pero con el desplazamiento REAL del objeto
entre la primera y la ultima observacion de su ventana: 1.35 px. O sea, prueba
que la tecnica alcanza a esa amplitud, no que se vea en datos reales, que es
parte de la tarea 27.

Todo corre sin red.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from astropy.time import Time
from astropy.wcs import WCS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import align as al  # noqa: E402
from core import flags as fl  # noqa: E402
from core import subtract as sb  # noqa: E402
from core import targets as tg  # noqa: E402
from core.datatypes import Frame  # noqa: E402

PIX_DEG = 6.2 / 3600.0
RUIDO = 1.0          # sigma por pixel
AMP = 30.0           # pico de la fuente: SNR ~30 por cuadro, una deteccion modesta


def make_wcs(ra, dec, ref_at):
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [ref_at[0] + 1, ref_at[1] + 1]
    w.wcs.cdelt = [-PIX_DEG, PIX_DEG]
    return w


def gauss(n, x0, y0, fwhm=2.0, amp=AMP):
    yy, xx = np.mgrid[0:n, 0:n]
    s = fwhm / 2.3548
    return amp * np.exp(-((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * s * s))


def make_frame(img, wcs, mjd, detector="D2", lam=1.5, bw=0.037, flag_bits=()):
    n = img.shape[0]
    flags = np.zeros((n, n), dtype=np.uint32)
    if flag_bits:
        flags[:, :] = fl.bitmask(list(flag_bits))
    return Frame(image=img, flags=flags, variance=np.full((n, n), RUIDO ** 2),
                 wcs=wcs, mjd=mjd, detector=detector, wavelength_um=lam,
                 bandwidth_um=bw)


def simple(lam=1.5, detector="D2", n=9, mjd=61000.0, valor=5.0, flag_bits=()):
    """Cuadro plano, para las pruebas de validacion y de aritmetica."""
    return make_frame(np.full((n, n), valor), make_wcs(10.0, 10.0, (4.0, 4.0)),
                      mjd, detector=detector, lam=lam, flag_bits=flag_bits)


# --------------------------------------------------------------------------
# Mitad 1 del "Listo cuando": solo mismo detector y lambda parecida
# --------------------------------------------------------------------------

def test_se_niega_a_restar_lo_que_no_es_comparable():
    a = simple(lam=1.500, detector="D2")

    # Otro detector.
    ok, motivo = sb.is_comparable(a, simple(lam=1.500, detector="D3"))
    assert not ok and "detectores distintos" in motivo

    # Lambda lejana: 0.3 um contra una tolerancia de 0.0185.
    ok, motivo = sb.is_comparable(a, simple(lam=1.800, detector="D2"))
    assert not ok and "longitud de onda" in motivo

    # Formas distintas.
    ok, motivo = sb.is_comparable(a, simple(lam=1.500, detector="D2", n=11))
    assert not ok and "formas distintas" in motivo

    # Y la resta levanta ValueError, no devuelve basura.
    for otro in (simple(lam=1.5, detector="D3"), simple(lam=1.8, detector="D2")):
        try:
            sb.subtract(a, otro)
        except ValueError as exc:
            assert "no se pueden restar" in str(exc)
        else:
            raise AssertionError("tendria que haberse negado")


def test_acepta_lambda_dentro_de_la_tolerancia():
    a = simple(lam=1.500)
    ok, motivo = sb.is_comparable(a, simple(lam=1.505))
    assert ok and motivo is None


def test_la_tolerancia_es_fraccion_del_ancho_de_banda():
    """Un numero fijo seria muy estricto en el rojo y muy laxo en el azul."""
    azul_a = simple(lam=1.200)
    azul_b = make_frame(np.full((9, 9), 5.0), make_wcs(10.0, 10.0, (4.0, 4.0)),
                        61000.0, lam=1.210, bw=0.030)
    rojo_a = make_frame(np.full((9, 9), 5.0), make_wcs(10.0, 10.0, (4.0, 4.0)),
                        61000.0, lam=4.800, bw=0.0375)
    rojo_b = make_frame(np.full((9, 9), 5.0), make_wcs(10.0, 10.0, (4.0, 4.0)),
                        61000.0, lam=4.810, bw=0.0375)
    # 0.010 um entra en los dos casos porque la tolerancia escala con el ancho.
    assert sb.is_comparable(azul_a, azul_b)[0]
    assert sb.is_comparable(rojo_a, rojo_b)[0]


def test_check_false_salta_la_validacion():
    a = simple(lam=1.5, detector="D2")
    b = simple(lam=1.5, detector="D3")
    diff, var, usable = sb.subtract(a, b, check=False)
    assert diff.shape == a.shape


def test_comparable_pairs_ordena_por_separacion_temporal():
    frames = [simple(mjd=61000.0), simple(mjd=61001.0), simple(mjd=61100.0)]
    pares = sb.comparable_pairs(frames)
    assert pares[0] == (0, 2), pares   # el par mas separado en el tiempo primero
    assert len(pares) == 3


def test_comparable_pairs_excluye_los_incompatibles():
    frames = [simple(detector="D2", mjd=61000.0),
              simple(detector="D2", mjd=61010.0),
              simple(detector="D5", mjd=61020.0)]
    pares = sb.comparable_pairs(frames)
    assert pares == [(0, 1)]


# --------------------------------------------------------------------------
# Aritmetica de la resta
# --------------------------------------------------------------------------

def test_la_resta_es_la_resta():
    a = simple(valor=10.0)
    b = simple(valor=4.0)
    diff, var, usable = sb.subtract(a, b)
    assert usable.all()
    assert np.allclose(diff, 6.0)


def test_las_varianzas_se_suman():
    diff, var, usable = sb.subtract(simple(valor=10.0), simple(valor=4.0))
    assert np.allclose(var, 2.0 * RUIDO ** 2)


def test_los_pixeles_enmascarados_quedan_nan():
    a = simple(valor=10.0, flag_bits=("HOT",))     # HOT se enmascara siempre
    b = simple(valor=4.0)
    diff, var, usable = sb.subtract(a, b)
    assert not usable.any()
    assert np.isnan(diff).all()


def test_source_no_invalida_la_resta_para_fotometria():
    """SOURCE marca la fuente: enmascararlo aca borraria el objetivo."""
    a = simple(valor=10.0, flag_bits=("SOURCE",))
    b = simple(valor=4.0, flag_bits=("SOURCE",))
    diff, var, usable = sb.subtract(a, b, mask_purpose="photometry")
    assert usable.all() and np.allclose(diff, 6.0)
    # Con la mascara de fondo, en cambio, no queda nada. Es lo correcto.
    diff2, _, usable2 = sb.subtract(a, b, mask_purpose="background")
    assert not usable2.any()


def test_los_nan_de_entrada_se_propagan():
    a = simple(valor=10.0)
    a.image = a.image.copy()
    a.image[0, 0] = np.nan
    diff, var, usable = sb.subtract(a, simple(valor=4.0))
    assert not usable[0, 0] and np.isnan(diff[0, 0])
    assert usable[1, 1]


# --------------------------------------------------------------------------
# Mitad 2 del "Listo cuando": el movimiento de WISE 0855 se ve
# --------------------------------------------------------------------------

VENTANA_WISE = ("2025-05-05", "2026-05-14")   # la ventana real, de coverage.yaml


def cuadros_wise0855_alineados_al_cielo(con_movimiento=True):
    """Dos cuadros sinteticos de WISE 0855, con su desplazamiento REAL.

    El WCS de cada cuadro apunta distinto, como pasa de verdad. La fuente se
    dibuja donde cae el objeto en esa fecha, mas estrellas de fondo fijas EN EL
    CIELO y ruido.
    """
    rng = np.random.default_rng(1234)
    n = 29
    ref_ra, ref_dec = tg.target_position("wise_0855", "2025-11-09")

    # Estrellas de fondo, en coordenadas de cielo (offsets fijos en grados).
    fondo_offsets = [(+0.008, +0.006), (-0.010, +0.004), (+0.003, -0.009)]

    frames = []
    for fecha, apuntado in zip(VENTANA_WISE, [(14.0, 14.0), (16.5, 12.2)]):
        w = make_wcs(ref_ra, ref_dec, apuntado)
        img = rng.normal(0.0, RUIDO, (n, n))

        # Las estrellas de fondo caen siempre en la misma posicion del cielo.
        for dra, ddec in fondo_offsets:
            bx, by = w.world_to_pixel_values(ref_ra + dra, ref_dec + ddec)
            if 0 <= bx < n and 0 <= by < n:
                img = img + gauss(n, bx, by, amp=2.0 * AMP)

        # El objetivo, donde esta ESA fecha (o quieto, si se pide sin movimiento).
        cuando = fecha if con_movimiento else VENTANA_WISE[0]
        ra, dec = tg.target_position("wise_0855", cuando)
        tx, ty = w.world_to_pixel_values(ra, dec)
        img = img + gauss(n, tx, ty, amp=AMP)

        frames.append(make_frame(img, w, float(Time(fecha).mjd)))
    return frames, (ref_ra, ref_dec)


def test_el_desplazamiento_sintetico_es_el_real():
    """Que la prueba use la amplitud de verdad, 1.35 px, y no una comoda."""
    arc, px = tg.drift_between("wise_0855", *VENTANA_WISE)
    assert 1.2 < px < 1.5, px


def test_el_movimiento_de_wise0855_se_ve_en_la_resta():
    """El "Listo cuando" de la tarea 22, y el objetivo O4 del enunciado."""
    frames, (ref_ra, ref_dec) = cuadros_wise0855_alineados_al_cielo()

    # Alinear AL CIELO: el fondo queda fijo y el objetivo se mueve.
    cubo = al.align_frames(frames, ra=ref_ra, dec=ref_dec)
    assert cubo.aligned_on == "sky"
    assert len(cubo) == 2, cubo.dropped

    diff, var, usable = sb.subtract_aligned(cubo, 1, 0)

    # El objetivo esta cerca de donde cae su posicion media, que es el centro.
    r = sb.dipole_snr(diff, var, center=cubo.center, box=4)
    assert r["detected"], (
        "no se detecto el dipolo: pos=" + format(r["pos_snr"], ".1f")
        + " neg=" + format(r["neg_snr"], ".1f")
        + " sep=" + format(r["separation_px"], ".2f") + " px"
    )
    assert r["pos_snr"] > 5 and r["neg_snr"] > 5, r
    # Los dos lobulos tienen que estar separados, no ser el mismo pixel.
    assert 0.5 < r["separation_px"] < 6.0, r["separation_px"]


def test_sin_movimiento_no_aparece_dipolo():
    """Contraprueba: si el objeto no se movio, no hay que inventar un dipolo."""
    frames, (ref_ra, ref_dec) = cuadros_wise0855_alineados_al_cielo(
        con_movimiento=False)
    cubo = al.align_frames(frames, ra=ref_ra, dec=ref_dec)
    diff, var, usable = sb.subtract_aligned(cubo, 1, 0)
    r = sb.dipole_snr(diff, var, center=cubo.center, box=4)
    assert not r["detected"], (
        "detecto movimiento donde no hay: pos=" + format(r["pos_snr"], ".1f")
        + " neg=" + format(r["neg_snr"], ".1f")
    )


def test_la_resta_sin_igualar_psf_deja_residuos():
    """Fija una limitacion MEDIDA, para que no se olvide.

    Sin igualar las PSF, dos cuadros remuestreados con corrimientos distintos
    quedan suavizados distinto, y la resta deja residuos alrededor de todas las
    fuentes del campo. Aca se mide cuanto, sin movimiento de por medio.

    Si esta prueba empieza a fallar es BUENA noticia: significa que alguien
    igualo las PSF, y entonces se puede bajar max_separation_px y subir la
    confianza de dipole_snr.
    """
    frames, (ra, dec) = cuadros_wise0855_alineados_al_cielo(con_movimiento=False)
    cubo = al.align_frames(frames, ra=ra, dec=dec)
    diff, var, usable = sb.subtract_aligned(cubo, 1, 0)
    snr = np.abs(diff) / np.sqrt(var)
    peor = float(np.nanmax(snr))
    assert peor > 3.0, (
        "el residuo de interpolacion bajo a " + format(peor, ".1f") + " sigma. "
        "Si es porque se igualaron las PSF, actualiza esta prueba y considera "
        "endurecer dipole_snr."
    )
    # Y aun con esos residuos, dipole_snr NO lo llama movimiento.
    r = sb.dipole_snr(diff, var, center=cubo.center, box=4)
    assert not r["detected"]


def test_restar_un_cubo_alineado_al_objetivo_se_rechaza():
    """La trampa: asi la resta cancela justo lo que se queria ver."""
    frames, _ = cuadros_wise0855_alineados_al_cielo()
    cubo = al.align_frames(frames, target_key="wise_0855")
    assert cubo.aligned_on == "target"
    try:
        sb.subtract_aligned(cubo, 1, 0)
    except ValueError as exc:
        assert "aligned_on='target'" in str(exc) and "ra=" in str(exc)
    else:
        raise AssertionError("tendria que avisar que el cubo esta mal alineado")


def test_se_puede_forzar_la_resta_de_un_cubo_centrado():
    """Para buscar variabilidad de brillo en vez de movimiento."""
    frames, _ = cuadros_wise0855_alineados_al_cielo()
    cubo = al.align_frames(frames, target_key="wise_0855")
    diff, var, usable = sb.subtract_aligned(cubo, 1, 0,
                                           warn_if_target_aligned=False)
    assert diff.shape == cubo.cube[0].shape


def test_dipole_snr_sin_datos_no_revienta():
    d = np.full((9, 9), np.nan)
    v = np.full((9, 9), np.nan)
    r = sb.dipole_snr(d, v)
    assert not r["detected"] and r["n_usable"] == 0
    assert not np.isfinite(r["pos_snr"])


def test_dipole_snr_ignora_un_solo_pico():
    """Un pico positivo solo puede ser un rayo cosmico, no movimiento."""
    d = np.zeros((15, 15))
    d[7, 7] = 100.0
    v = np.ones((15, 15))
    r = sb.dipole_snr(d, v, center=(7.0, 7.0), box=4)
    assert r["pos_snr"] > 50
    assert not r["detected"], "hace falta el par positivo-negativo, no un pico"


# --------------------------------------------------------------------------
# coadd
# --------------------------------------------------------------------------

def cubo_plano(n_frames=4, valor=8.0, n=9, lam=1.5, detector="D2"):
    frames = [make_frame(np.full((n, n), valor),
                         make_wcs(10.0, 10.0, (4.0, 4.0)),
                         61000.0 + k, detector=detector, lam=lam)
              for k in range(n_frames)]
    return al.align_frames(frames, ra=10.0, dec=10.0)


def test_coadd_promedia_y_baja_la_varianza():
    cubo = cubo_plano(n_frames=4, valor=8.0)
    img, var, n_eff = sb.coadd(cubo)
    interior = (slice(2, -2), slice(2, -2))
    assert np.allclose(img[interior], 8.0, atol=1e-4)
    # 4 medidas de varianza 1 -> varianza 1/4
    assert np.allclose(var[interior], RUIDO ** 2 / 4.0, atol=1e-5)
    assert np.allclose(n_eff[interior], 4.0, atol=1e-5)


def test_coadd_n_eff_baja_si_un_cuadro_domina():
    """n_eff es el numero EFECTIVO, no la cuenta de cuadros."""
    cubo = cubo_plano(n_frames=2, valor=8.0)
    cubo.variance = cubo.variance.copy()
    cubo.variance[1] = cubo.variance[1] * 100.0   # un cuadro mucho peor
    img, var, n_eff = sb.coadd(cubo)
    interior = (slice(2, -2), slice(2, -2))
    assert n_eff[interior].max() < 1.1, n_eff[interior].max()


def test_coadd_se_niega_a_mezclar_detectores():
    """La consideracion C8 no puede ser apilar los 6 detectores."""
    f1 = make_frame(np.full((9, 9), 8.0), make_wcs(10.0, 10.0, (4.0, 4.0)),
                    61000.0, detector="D2", lam=1.5)
    f2 = make_frame(np.full((9, 9), 8.0), make_wcs(10.0, 10.0, (4.0, 4.0)),
                    61001.0, detector="D5", lam=4.1)
    cubo = al.align_frames([f1, f2], ra=10.0, dec=10.0)
    try:
        sb.coadd(cubo)
    except ValueError as exc:
        assert "detectores distintos" in str(exc)
    else:
        raise AssertionError("tendria que negarse a apilar detectores distintos")


def test_coadd_respeta_indices():
    cubo = cubo_plano(n_frames=4)
    img, var, n_eff = sb.coadd(cubo, indices=[0, 1])
    interior = (slice(2, -2), slice(2, -2))
    assert np.allclose(n_eff[interior], 2.0, atol=1e-5)


def test_coadd_ignora_pixeles_enmascarados():
    cubo = cubo_plano(n_frames=2)
    cubo.flags = cubo.flags.copy()
    cubo.flags[0] = cubo.flags[0] | np.uint32(fl.bitmask(["HOT"]))
    img, var, n_eff = sb.coadd(cubo)
    interior = (slice(2, -2), slice(2, -2))
    assert np.allclose(n_eff[interior], 1.0, atol=1e-5), "deberia quedar 1 cuadro"


def test_coadd_cubo_vacio_falla_claro():
    cubo = cubo_plano(n_frames=1)
    cubo.cube = cubo.cube[:0]
    try:
        sb.coadd(cubo)
    except ValueError as exc:
        assert "vacio" in str(exc)
    else:
        raise AssertionError("un cubo vacio tendria que fallar")


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
