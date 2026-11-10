"""Pruebas de core/align.py. Tarea 21.

    python core/test_align.py       # sin pytest
    pytest core/test_align.py       # con pytest

La prueba que cierra la tarea es `test_wise0855_queda_centrado_en_cada_fecha`,
que es literalmente el "Listo cuando" del Tablero. Y la que le da sentido es
`test_sin_correccion_de_movimiento_propio_queda_descentrado`: comprueba que la
correccion hace trabajo real, porque si no, centrar seria trivial y no probaria
nada.

Todo corre sin red: los WCS se construyen a mano y las posiciones salen de
config/targets.yaml, que ya esta en el repo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from astropy.wcs import WCS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import align as al  # noqa: E402
from core import flags as fl  # noqa: E402
from core import targets as tg  # noqa: E402
from core.datatypes import Frame  # noqa: E402

PIX_DEG = 6.2 / 3600.0   # escala de placa de SPHEREx


def make_wcs(ra, dec, target_at):
    """WCS TAN donde (ra, dec) cae exactamente en el pixel `target_at` (base 0)."""
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [target_at[0] + 1, target_at[1] + 1]   # CRPIX es base 1
    w.wcs.cdelt = [-PIX_DEG, PIX_DEG]
    return w


def gauss(n, x0, y0, fwhm=2.0, amp=100.0):
    """Una fuente puntual gaussiana, para poder medir su centroide."""
    yy, xx = np.mgrid[0:n, 0:n]
    s = fwhm / 2.3548
    return amp * np.exp(-((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * s * s))


def make_frame(ra, dec, mjd, target_at, n=29, detector="D2", lam=1.5,
               bw=0.037, flag_bits=(), source=True):
    """Un Frame sintetico con la fuente dibujada en `target_at`."""
    img = gauss(n, target_at[0], target_at[1]) if source else np.zeros((n, n))
    flags = np.zeros((n, n), dtype=np.uint32)
    if flag_bits:
        flags[:, :] = fl.bitmask(list(flag_bits))
    return Frame(
        image=img, flags=flags, variance=np.full((n, n), 4.0),
        wcs=make_wcs(ra, dec, target_at), mjd=mjd, detector=detector,
        wavelength_um=lam, bandwidth_um=bw,
    )


# --------------------------------------------------------------------------
# target_pixel
# --------------------------------------------------------------------------

def test_target_pixel_encuentra_la_posicion_del_wcs():
    f = make_frame(133.76, -7.242, 61000.0, target_at=(7.0, 19.0))
    x, y = al.target_pixel(f, ra=133.76, dec=-7.242)
    assert abs(x - 7.0) < 1e-6 and abs(y - 19.0) < 1e-6


def test_target_pixel_sin_wcs_falla_claro():
    f = make_frame(10.0, 10.0, 61000.0, target_at=(5.0, 5.0))
    f.wcs = None
    try:
        al.target_pixel(f, ra=10.0, dec=10.0)
    except ValueError as exc:
        assert "WCS" in str(exc)
    else:
        raise AssertionError("tendria que haber fallado sin WCS")


def test_target_pixel_exige_objetivo():
    f = make_frame(10.0, 10.0, 61000.0, target_at=(5.0, 5.0))
    try:
        al.target_pixel(f)
    except ValueError as exc:
        assert "target_key" in str(exc)
    else:
        raise AssertionError("tendria que exigir target_key o ra/dec")


# --------------------------------------------------------------------------
# El criterio de aceptacion del Tablero
# --------------------------------------------------------------------------

FECHAS = ["2025-05-05", "2025-08-14", "2025-11-20", "2026-02-28", "2026-05-14"]
# Posiciones arbitrarias y distintas en cada cuadro, simulando que cada
# exposicion apunta distinto.
POSICIONES = [(6.0, 21.0), (18.4, 9.7), (14.0, 14.0), (22.3, 17.1), (8.8, 5.5)]


def frames_de_wise0855():
    """Cuadros sinteticos de WISE 0855 en su posicion REAL de cada fecha."""
    from astropy.time import Time
    frames = []
    for fecha, pos in zip(FECHAS, POSICIONES):
        ra, dec = tg.target_position("wise_0855", fecha)
        frames.append(make_frame(ra, dec, float(Time(fecha).mjd), target_at=pos))
    return frames


def test_wise0855_queda_centrado_en_cada_fecha():
    """El "Listo cuando" de la tarea 21, tal cual."""
    frames = frames_de_wise0855()
    cubo = al.align_frames(frames, target_key="wise_0855")

    assert len(cubo) == len(frames), cubo.dropped
    cx, cy = cubo.center
    assert (cx, cy) == (14.0, 14.0)   # centro de un recorte de 29x29

    for i in range(len(cubo)):
        x, y = al.centroid(cubo.cube[i], center=cubo.center)
        assert abs(x - cx) < 0.1 and abs(y - cy) < 0.1, (
            "cuadro " + str(i) + " (" + FECHAS[i] + ") quedo descentrado en ("
            + format(x, ".2f") + ", " + format(y, ".2f") + "), se esperaba ("
            + format(cx, ".1f") + ", " + format(cy, ".1f") + ")"
        )


def test_sin_correccion_de_movimiento_propio_queda_descentrado():
    """Lo que le da sentido a la prueba anterior.

    Si se alinea contra las coordenadas de catalogo J2000 en vez de propagarlas,
    la fuente NO queda centrada: queda corrida por la deriva del objeto. Sin
    esta prueba, centrar podria estar funcionando por casualidad.
    """
    frames = frames_de_wise0855()
    a = tg.get_target("wise_0855")["astrometry"]

    cubo = al.align_frames(frames, ra=a["ra_deg"], dec=a["dec_deg"],
                           drop_if_outside=False)
    # La deriva es de ~35 px, mucho mas que el recorte de 29: la fuente se cae
    # del cuadro, asi que no hay centroide que medir.
    assert len(cubo) == len(frames)
    for i in range(len(cubo)):
        x, y = al.centroid(cubo.cube[i], center=cubo.center)
        centrado = np.isfinite(x) and abs(x - cubo.center[0]) < 0.5
        assert not centrado, (
            "el cuadro " + str(i) + " quedo centrado SIN corregir movimiento "
            "propio; la prueba de arriba no estaria probando nada"
        )


def test_shift_series_coincide_con_lo_que_aplica_align():
    frames = frames_de_wise0855()
    shifts, mjds = al.shift_series(frames, target_key="wise_0855")
    cubo = al.align_frames(frames, target_key="wise_0855")
    assert np.allclose(shifts, cubo.shifts_px)
    assert np.allclose(mjds, cubo.mjds)


def test_sale_ordenado_por_fecha():
    frames = frames_de_wise0855()
    revueltos = [frames[3], frames[0], frames[4], frames[1], frames[2]]
    cubo = al.align_frames(revueltos, target_key="wise_0855")
    assert np.all(np.diff(cubo.mjds) > 0)


# --------------------------------------------------------------------------
# Remuestreo: imagen, varianza y flags
# --------------------------------------------------------------------------

def test_corrimiento_entero_es_exacto():
    """Con un corrimiento de pixeles enteros no hay interpolacion que perder."""
    f = make_frame(50.0, 20.0, 61000.0, target_at=(10.0, 12.0))
    cubo = al.align_frames([f], ra=50.0, dec=20.0)
    original = gauss(29, 14.0, 14.0)
    movido = cubo.cube[0]
    bueno = np.isfinite(movido)
    assert np.allclose(movido[bueno], original[bueno], atol=1e-4)


def test_varianza_se_propaga_con_pesos_al_cuadrado():
    """Medio pixel de corrimiento reparte el peso y baja la varianza."""
    f = make_frame(50.0, 20.0, 61000.0, target_at=(14.5, 14.5))
    cubo = al.align_frames([f], ra=50.0, dec=20.0)
    v = cubo.variance[0]
    interior = v[5:-5, 5:-5]
    # 4 esquinas con peso 0.25: var_out = 4 * 0.25^2 * 4.0 = 1.0
    assert np.allclose(interior, 1.0, atol=1e-5), np.nanmedian(interior)


def test_varianza_no_cambia_si_no_hay_interpolacion():
    f = make_frame(50.0, 20.0, 61000.0, target_at=(10.0, 12.0))
    cubo = al.align_frames([f], ra=50.0, dec=20.0)
    v = cubo.variance[0]
    assert np.allclose(v[np.isfinite(v)], 4.0, atol=1e-5)


def test_flags_no_se_interpolan_y_no_inventan_bits():
    """Interpolar un bitmap crearia combinaciones que nunca existieron."""
    f = make_frame(50.0, 20.0, 61000.0, target_at=(14.5, 14.5),
                   flag_bits=("SOURCE", "HOT"))
    cubo = al.align_frames([f], ra=50.0, dec=20.0)
    flg = cubo.flags[0]
    esperado = fl.bitmask(["SOURCE", "HOT"])
    sin_missing = flg & ~np.uint32(1 << fl.bit_of("MISSING_DATA"))
    presentes = set(np.unique(sin_missing).tolist())
    assert presentes <= {0, esperado}, (
        "aparecieron combinaciones de bits que no estaban: " + repr(presentes)
    )
    assert flg.dtype == np.uint32


def test_flags_marcan_los_pixeles_sin_dato():
    """Donde el remuestreo no alcanza, se dice MISSING_DATA, no se calla."""
    f = make_frame(50.0, 20.0, 61000.0, target_at=(3.0, 3.0), flag_bits=("SOURCE",))
    cubo = al.align_frames([f], ra=50.0, dec=20.0)
    img, flg = cubo.cube[0], cubo.flags[0]
    sin_dato = ~np.isfinite(img)
    assert sin_dato.any(), "este corrimiento tendria que dejar zona sin dato"
    assert fl.has_any(flg[sin_dato], ["MISSING_DATA"]).all(), (
        "hay pixeles NaN sin el bit MISSING_DATA: el backend no se enteraria"
    )


def test_los_pixeles_sin_dato_los_excluye_la_mascara_sola():
    """La razon de usar MISSING_DATA y no un campo aparte."""
    f = make_frame(50.0, 20.0, 61000.0, target_at=(3.0, 3.0))
    cubo = al.align_frames([f], ra=50.0, dec=20.0)
    malos = fl.mask_for(cubo.flags[0], "photometry")
    sin_dato = ~np.isfinite(cubo.cube[0])
    assert malos[sin_dato].all(), "mask_for() deberia excluir los NaN sin ayuda"


def test_el_borde_queda_nan_sin_renormalizar():
    """Mejor un borde de NaN predecible que valores atenuados a medias."""
    f = make_frame(50.0, 20.0, 61000.0, target_at=(14.5, 14.5))
    cubo = al.align_frames([f], ra=50.0, dec=20.0)
    img = cubo.cube[0]
    assert not np.isfinite(img[0, :]).all() or not np.isfinite(img[:, 0]).all()
    assert np.isfinite(img[5:-5, 5:-5]).all(), "el interior no deberia tener NaN"


# --------------------------------------------------------------------------
# Forma, descartes y validacion
# --------------------------------------------------------------------------

def test_out_shape_recorta():
    frames = frames_de_wise0855()
    cubo = al.align_frames(frames, target_key="wise_0855", out_shape=(11, 11))
    assert cubo.cube.shape == (len(frames), 11, 11)
    assert cubo.center == (5.0, 5.0)
    x, y = al.centroid(cubo.cube[0], center=cubo.center)
    assert abs(x - 5.0) < 0.1 and abs(y - 5.0) < 0.1


def test_out_shape_por_defecto_es_el_recorte_mas_chico():
    f1 = make_frame(50.0, 20.0, 61000.0, target_at=(14.0, 14.0), n=29)
    f2 = make_frame(50.0, 20.0, 61001.0, target_at=(10.0, 10.0), n=21)
    cubo = al.align_frames([f1, f2], ra=50.0, dec=20.0)
    assert cubo.cube.shape == (2, 21, 21)


def test_descarta_cuadros_donde_el_objetivo_no_entra():
    dentro = make_frame(50.0, 20.0, 61000.0, target_at=(14.0, 14.0))
    fuera = make_frame(50.0, 20.0, 61001.0, target_at=(14.0, 14.0))
    # Mover el WCS para que el objetivo caiga muy afuera del recorte.
    fuera.wcs = make_wcs(50.0, 20.0, (200.0, 200.0))
    cubo = al.align_frames([dentro, fuera], ra=50.0, dec=20.0)
    assert len(cubo) == 1
    assert len(cubo.dropped) == 1
    assert "fuera del recorte" in cubo.dropped[0]["reason"]
    assert cubo.dropped[0]["mjd"] == 61001.0


def test_drop_if_outside_false_los_conserva():
    f = make_frame(50.0, 20.0, 61000.0, target_at=(14.0, 14.0))
    f.wcs = make_wcs(50.0, 20.0, (200.0, 200.0))
    cubo = al.align_frames([f], ra=50.0, dec=20.0, drop_if_outside=False)
    assert len(cubo) == 1 and not cubo.dropped
    assert not np.isfinite(cubo.cube[0]).any(), "no deberia haber dato valido"


def test_cubo_vacio_no_revienta():
    f = make_frame(50.0, 20.0, 61000.0, target_at=(14.0, 14.0))
    f.wcs = make_wcs(50.0, 20.0, (500.0, 500.0))
    cubo = al.align_frames([f], ra=50.0, dec=20.0)
    assert len(cubo) == 0
    assert cubo.cube.shape == (0, 29, 29)
    assert len(cubo.dropped) == 1


def test_lista_vacia_falla():
    try:
        al.align_frames([], ra=1.0, dec=1.0)
    except ValueError as exc:
        assert "cuadros" in str(exc)
    else:
        raise AssertionError("una lista vacia tendria que fallar")


def test_sin_objetivo_falla():
    f = make_frame(50.0, 20.0, 61000.0, target_at=(14.0, 14.0))
    try:
        al.align_frames([f])
    except ValueError as exc:
        assert "target_key" in str(exc)
    else:
        raise AssertionError("tendria que exigir objetivo")


def test_mezclar_detectores_se_permite_para_video():
    """Para un VIDEO mezclar detectores es legitimo; para restar no."""
    f1 = make_frame(50.0, 20.0, 61000.0, target_at=(14.0, 14.0), detector="D2")
    f2 = make_frame(50.0, 20.0, 61001.0, target_at=(12.0, 16.0), detector="D3",
                    lam=2.0)
    cubo = al.align_frames([f1, f2], ra=50.0, dec=20.0)
    assert len(cubo) == 2
    assert cubo.detectors == ["D2", "D3"]
    assert np.allclose(cubo.wavelengths_um, [1.5, 2.0])


def test_require_same_detector_falla_si_se_mezclan():
    f1 = make_frame(50.0, 20.0, 61000.0, target_at=(14.0, 14.0), detector="D2")
    f2 = make_frame(50.0, 20.0, 61001.0, target_at=(12.0, 16.0), detector="D3")
    try:
        al.align_frames([f1, f2], ra=50.0, dec=20.0, require_same_detector=True)
    except ValueError as exc:
        assert "D2" in str(exc) and "D3" in str(exc)
    else:
        raise AssertionError("tendria que negarse a mezclar detectores")


# --------------------------------------------------------------------------
# centroid
# --------------------------------------------------------------------------

def test_centroid_encuentra_una_fuente_desplazada():
    img = gauss(29, 16.3, 11.8)
    x, y = al.centroid(img, center=(16.0, 12.0))
    assert abs(x - 16.3) < 0.1 and abs(y - 11.8) < 0.1


def test_centroid_sin_flujo_devuelve_nan():
    x, y = al.centroid(np.zeros((9, 9)))
    assert not np.isfinite(x) and not np.isfinite(y)


def test_centroid_ignora_nan():
    img = gauss(29, 14.0, 14.0)
    img[0, 0] = np.nan
    x, y = al.centroid(img, center=(14.0, 14.0))
    assert abs(x - 14.0) < 0.05 and abs(y - 14.0) < 0.05


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
