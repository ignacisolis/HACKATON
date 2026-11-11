"""Resta y suma de imagenes comparables. Tarea 22, consideracion C5.

Rol C (Ciencia). Funciones puras: reciben arrays, devuelven arrays.

La regla que no se puede romper
------------------------------
**No se restan imagenes de distinta longitud de onda.** En SPHEREx el filtro
varia a lo largo del detector, asi que cada exposicion mide el objetivo en una
lambda concreta. Restar dos exposiciones de lambdas distintas no da "lo que
cambio en el tiempo": da la diferencia entre dos colores, que para un objeto
rojo puede ser gigante y no significa nada.

Por eso `subtract()` valida antes de operar y se niega a restar lo que no es
comparable. La validacion se puede consultar aparte con `is_comparable()`.

Y la que tampoco
----------------
**Hay que restar cuadros alineados AL CIELO, no al objetivo.** Si el cubo se
alineo con `target_key`, el objetivo esta en el mismo pixel en los dos cuadros y
la resta lo cancela: el movimiento no se ve y la imagen queda vacia, que parece
un resultado correcto. Para ver movimiento hay que alinear con `ra`/`dec` fijos,
asi el fondo queda quieto y el objeto deja un dipolo.

`subtract_aligned()` mira `cube.aligned_on` y avisa cuando no corresponde.

Para que sirve, en concreto
--------------------------
WISE 0855 se mueve solo 1.35 px entre su primera y su ultima observacion (ver
docs/ciencia.md 3.2). Eso en un video no se ve. En una resta deja un dipolo:
negativo donde estaba, positivo donde esta. Esa es la forma de cumplir el
objetivo O4 del enunciado, y `dipole_snr()` lo mide.
"""
from __future__ import annotations

import numpy as np

from core import flags as fl
from core.datatypes import AlignedCube, Frame  # noqa: F401

# Tolerancia por defecto para considerar dos exposiciones "de la misma banda".
# Criterio: una fraccion del ancho de banda del propio cuadro. Con R ~ 40 en el
# azul el ancho es ~0.03 um a 1.2 um, y con R ~ 128 en el rojo es ~0.04 um a
# 5 um. Usar una fraccion del ancho en vez de un numero fijo evita ser
# demasiado estricto en el rojo y demasiado laxo en el azul.
MAX_DLAMBDA_FRACTION = 0.5


# --------------------------------------------------------------------------
# Validacion
# --------------------------------------------------------------------------

def _comparables(det_a, det_b, lam_a, lam_b, bw_a, bw_b, shape_a, shape_b, frac):
    """Nucleo de la validacion, sobre valores sueltos. Puro."""
    if det_a != det_b:
        return False, ("detectores distintos: " + str(det_a) + " vs " + str(det_b)
                       + "; miden longitudes de onda distintas")
    if shape_a != shape_b:
        return False, ("formas distintas: " + str(shape_a) + " vs " + str(shape_b))
    dlam = abs(float(lam_a) - float(lam_b))
    tol = frac * min(float(bw_a), float(bw_b))
    # Epsilon relativo para que un caso que cae justo en el borde no dependa del
    # error de coma flotante: 1.215 - 1.200 da 0.015000000000000124, que es
    # "mayor" que una tolerancia de 0.015 por 1e-16.
    if dlam > tol * (1.0 + 1e-9):
        return False, ("diferencia de longitud de onda " + format(dlam, ".4f")
                       + " um, mayor que la tolerancia " + format(tol, ".4f") + " um")
    return True, None


def is_comparable(a, b, max_dlambda_fraction=MAX_DLAMBDA_FRACTION):
    """Dice si dos Frame se pueden restar, y por que no si no se pueden.

    PURA. Devuelve (bool, motivo). El motivo es None cuando si se pueden.

    Condiciones:
      1. Mismo detector. Detectores distintos miden rangos distintos: no se
         solapan, se encadenan (docs/ciencia.md 3.4).
      2. Longitud de onda parecida, dentro de una fraccion del ancho de banda.
      3. Misma forma de array.
    """
    return _comparables(a.detector, b.detector, a.wavelength_um, b.wavelength_um,
                        a.bandwidth_um, b.bandwidth_um, a.shape, b.shape,
                        max_dlambda_fraction)


def comparable_pairs(frames, max_dlambda_fraction=MAX_DLAMBDA_FRACTION):
    """Todos los pares de `frames` que se pueden restar entre si.

    PURA. Devuelve lista de (i, j) con i < j, ordenada por separacion temporal
    decreciente: los pares mas separados en el tiempo primero, que son los que
    mejor muestran el movimiento.

    Es lo que el backend necesita para ofrecerle al usuario que restar. Con 2 o 3
    epocas por banda (docs/ciencia.md 3.3) la lista va a ser corta para WISE
    0855 y eps Ind B, y larga para R Dra.

    Acepta una lista de Frame o un AlignedCube.
    """
    if isinstance(frames, AlignedCube):
        n = len(frames)
        def datos(i):
            return (frames.detectors[i], frames.wavelengths_um[i],
                    frames.bandwidths_um[i], frames.cube[i].shape, frames.mjds[i])
    else:
        n = len(frames)
        def datos(i):
            f = frames[i]
            return (f.detector, f.wavelength_um, f.bandwidth_um, f.shape, f.mjd)

    pairs = []
    for i in range(n):
        di = datos(i)
        for j in range(i + 1, n):
            dj = datos(j)
            ok, _ = _comparables(di[0], dj[0], di[1], dj[1], di[2], dj[2],
                                 di[3], dj[3], max_dlambda_fraction)
            if ok:
                pairs.append((i, j))
    pairs.sort(key=lambda p: -abs(datos(p[1])[4] - datos(p[0])[4]))
    return pairs


# --------------------------------------------------------------------------
# Resta
# --------------------------------------------------------------------------

def _diferencia(img_a, img_b, var_a, var_b, flg_a, flg_b, mask_purpose):
    """La resta en si, sobre arrays. Pura."""
    malos = fl.mask_for(flg_a, mask_purpose) | fl.mask_for(flg_b, mask_purpose)
    finitos = np.isfinite(img_a) & np.isfinite(img_b)
    usable = finitos & ~malos

    diff = np.where(usable, np.asarray(img_a, float) - np.asarray(img_b, float), np.nan)
    # Las varianzas se suman: son dos medidas independientes.
    var = np.where(usable,
                   np.nan_to_num(np.asarray(var_a, float))
                   + np.nan_to_num(np.asarray(var_b, float)),
                   np.nan)
    return diff, var, usable


def subtract(a, b, max_dlambda_fraction=MAX_DLAMBDA_FRACTION, check=True,
             mask_purpose="photometry"):
    """Resta b de a, previa validacion. Devuelve (diferencia, varianza, usable).

    PURA: recibe dos Frame YA ALINEADOS, devuelve arrays. Alinear es tarea de
    core.align; si se restan cuadros sin alinear, el residuo es el error de
    apuntado, no el cambio del objeto.

    Parametros
    ----------
    a, b : Frame
        Ya alineados sobre la misma referencia y con la misma forma.
    check : bool
        Si es False, salta la validacion. Solo para experimentar a mano; el
        backend nunca deberia pasarlo en False.
    mask_purpose : str
        Que mascara de FLAGS aplicar, 'photometry' o 'background'. Ver
        core.flags: enmascarar SOURCE borraria el objetivo.

    Devuelve
    --------
    diff : ndarray 2D   a.image - b.image, NaN donde no se puede confiar
    var : ndarray 2D    a.variance + b.variance
    usable : ndarray 2D de bool

    Levanta
    -------
    ValueError si los cuadros no son comparables. El mensaje dice por que.
    """
    if check:
        ok, motivo = is_comparable(a, b, max_dlambda_fraction)
        if not ok:
            raise ValueError("no se pueden restar estos cuadros: " + motivo)
    return _diferencia(a.image, b.image, a.variance, b.variance,
                       a.flags, b.flags, mask_purpose)


def subtract_aligned(cube, i, j, max_dlambda_fraction=MAX_DLAMBDA_FRACTION,
                     check=True, mask_purpose="photometry",
                     warn_if_target_aligned=True):
    """Resta el cuadro j del cuadro i de un AlignedCube.

    PURA. Es el camino normal: el backend alinea una vez y resta pares del cubo.

    `warn_if_target_aligned` levanta ValueError si el cubo se alineo sobre el
    objetivo, porque entonces la resta cancela justamente lo que se queria ver.
    Para medir movimiento hay que alinear al cielo, con ra/dec fijos. Se puede
    desactivar si de verdad se quiere restar un cubo centrado en el objetivo,
    por ejemplo para buscar variabilidad de brillo en vez de movimiento.
    """
    if warn_if_target_aligned and getattr(cube, "aligned_on", None) == "target":
        raise ValueError(
            "este cubo se alineo sobre el objetivo (aligned_on='target'), asi que "
            "la resta lo cancela y el movimiento no se ve. Para ver movimiento "
            "alinea al cielo: align_frames(frames, ra=..., dec=...). Si de verdad "
            "queres restar un cubo centrado en el objetivo, pasa "
            "warn_if_target_aligned=False."
        )
    if check:
        ok, motivo = _comparables(
            cube.detectors[i], cube.detectors[j],
            cube.wavelengths_um[i], cube.wavelengths_um[j],
            cube.bandwidths_um[i], cube.bandwidths_um[j],
            cube.cube[i].shape, cube.cube[j].shape, max_dlambda_fraction,
        )
        if not ok:
            raise ValueError("no se pueden restar los cuadros " + str(i) + " y "
                             + str(j) + ": " + motivo)
    return _diferencia(cube.cube[i], cube.cube[j], cube.variance[i],
                       cube.variance[j], cube.flags[i], cube.flags[j],
                       mask_purpose)


# --------------------------------------------------------------------------
# Suma ponderada
# --------------------------------------------------------------------------

def coadd(cube, indices=None, mask_purpose="photometry", check=True,
          max_dlambda_fraction=MAX_DLAMBDA_FRACTION):
    """Suma ponderada de cuadros comparables, para mejorar senal/ruido.

    PURA. Pondera por 1/varianza, que es lo optimo para ruido gaussiano.

    Recibe un AlignedCube, no una lista de Frame: apilar cuadros sin alinear no
    tiene sentido. Lo normal es que el cubo este alineado sobre el OBJETIVO.

    OJO con la consideracion C8 del enunciado. "Combinar los 6 detectores para
    mejorar la senal/ruido" NO puede significar apilar los 6 detectores sobre la
    misma banda: cada uno mide longitudes de onda distintas y no se solapan
    (docs/ciencia.md 3.4). La mejora sale de combinar VISITAS REPETIDAS a la
    misma banda, que es lo que hace esta funcion. Lo que aportan los 6
    detectores es extender el espectro, no profundizarlo.

    Parametros
    ----------
    cube : AlignedCube
    indices : lista de int, opcional
        Que cuadros combinar. Por defecto, todos.
    check : bool
        Verifica que todos los cuadros elegidos sean comparables entre si.

    Devuelve
    --------
    img : ndarray 2D     promedio ponderado, NaN donde ningun cuadro aporto
    var : ndarray 2D     1 / suma de pesos
    n_eff : ndarray 2D   numero efectivo de cuadros por pixel

    `n_eff` es (sum w)^2 / sum w^2, no la cuenta de cuadros: dice cuantas
    medidas equivalentes de igual peso entraron en cada pixel. Si un cuadro
    domina por tener mucha menos varianza, n_eff baja, y eso es lo honesto.
    """
    if len(cube) == 0:
        raise ValueError("el cubo esta vacio: no hay nada que apilar")
    idx = list(range(len(cube))) if indices is None else list(indices)
    if not idx:
        raise ValueError("no se eligio ningun cuadro")

    if check and len(idx) > 1:
        i0 = idx[0]
        for j in idx[1:]:
            ok, motivo = _comparables(
                cube.detectors[i0], cube.detectors[j],
                cube.wavelengths_um[i0], cube.wavelengths_um[j],
                cube.bandwidths_um[i0], cube.bandwidths_um[j],
                cube.cube[i0].shape, cube.cube[j].shape, max_dlambda_fraction,
            )
            if not ok:
                raise ValueError("no se puede apilar el cuadro " + str(j)
                                 + " con el " + str(i0) + ": " + motivo)

    forma = cube.cube[0].shape
    suma_wv = np.zeros(forma, dtype=float)
    suma_w = np.zeros(forma, dtype=float)
    suma_w2 = np.zeros(forma, dtype=float)

    for k in idx:
        img = np.asarray(cube.cube[k], dtype=float)
        var = np.asarray(cube.variance[k], dtype=float)
        malos = fl.mask_for(cube.flags[k], mask_purpose)
        bueno = np.isfinite(img) & np.isfinite(var) & (var > 0) & ~malos
        w = np.where(bueno, 1.0 / np.where(var > 0, var, 1.0), 0.0)
        suma_wv += np.where(bueno, img * w, 0.0)
        suma_w += w
        suma_w2 += w * w

    hay = suma_w > 0
    img = np.where(hay, suma_wv / np.where(hay, suma_w, 1.0), np.nan)
    var = np.where(hay, 1.0 / np.where(hay, suma_w, 1.0), np.nan)
    n_eff = np.where(suma_w2 > 0, suma_w ** 2 / np.where(suma_w2 > 0, suma_w2, 1.0), 0.0)
    return img, var, n_eff


# --------------------------------------------------------------------------
# Medir el dipolo: el objetivo O4
# --------------------------------------------------------------------------

def dipole_snr(diff, var, center=None, box=4, min_snr=3.0,
               max_separation_px=4.0):
    """Mide el dipolo que deja un objeto en movimiento en una resta.

    PURA. Un objeto que se corrio deja dos lobulos en la diferencia: positivo
    donde esta ahora y negativo donde estaba. Esta funcion los busca en una caja
    alrededor de `center` y devuelve cuan significativos son.

    Es la forma de cumplir el objetivo O4 ("hacer visible el movimiento") para
    WISE 0855, que se desplaza 1.35 px en toda la ventana de datos: en un video
    eso no se ve, pero el dipolo si se mide.

    Devuelve un dict con:
      pos_snr        significancia del lobulo positivo, en sigmas
      neg_snr        idem del negativo (valor positivo)
      pos_xy, neg_xy posicion de cada lobulo, en pixeles
      separation_px  distancia entre los dos lobulos
      detected       True si parece un dipolo de verdad (ver abajo)
      n_usable       pixeles con dato en la caja

    Que cuenta como detectado, y por que
    ------------------------------------
    Hacen falta TRES cosas, no solo que haya senal:

    1. Los DOS lobulos por encima de `min_snr`. Un solo pico positivo puede ser
       un rayo cosmico o una fuente que cambio de brillo, no algo que se movio.
    2. Los dos lobulos **juntos**, a menos de `max_separation_px`. Una fuente
       puntual desplazada deja el positivo y el negativo pegados, separados por
       mas o menos lo que se movio. Dos picos significativos en esquinas
       opuestas de la caja no son un dipolo: son dos cosas distintas.
    3. Separacion mayor que cero.

    El punto 2 salio de medirlo: con el desplazamiento real de WISE 0855 los
    lobulos quedan a 2.0 px; en un par SIN movimiento aparecian dos picos de 3.5
    y 6.2 sigma pero a 8.1 px, en esquinas opuestas. Sin el limite de
    separacion, eso pasaba por deteccion.

    LIMITACION, y es importante
    ---------------------------
    Esto es resta directa, SIN igualar las PSF. Si los dos cuadros se
    remuestrearon con corrimientos distintos, uno queda mas suavizado que el
    otro, y la diferencia deja residuos alrededor de TODAS las fuentes del campo,
    no solo del objetivo. En la prueba sin movimiento esos residuos llegaron a
    6 sigma.

    O sea: `detected` dice "hay algo con forma de dipolo aca", no "este objeto se
    movio con certeza". Para una medicion publicable hay que convolucionar los
    dos cuadros a una PSF comun, y para eso esta la extension PSF de los FITS.
    Queda para la tarea 27, cuando se valide con datos reales.
    """
    d = np.asarray(diff, dtype=float)
    v = np.asarray(var, dtype=float)
    ny, nx = d.shape
    if center is None:
        center = ((nx - 1) / 2.0, (ny - 1) / 2.0)
    cx, cy = center

    x0 = max(0, int(np.floor(cx - box)))
    x1 = min(nx, int(np.ceil(cx + box)) + 1)
    y0 = max(0, int(np.floor(cy - box)))
    y1 = min(ny, int(np.ceil(cy + box)) + 1)

    sub_d = d[y0:y1, x0:x1]
    sub_v = v[y0:y1, x0:x1]
    bueno = np.isfinite(sub_d) & np.isfinite(sub_v) & (sub_v > 0)
    vacio = {
        "pos_snr": float("nan"), "neg_snr": float("nan"),
        "pos_xy": (float("nan"), float("nan")),
        "neg_xy": (float("nan"), float("nan")),
        "separation_px": float("nan"), "detected": False,
        "n_usable": int(bueno.sum()),
    }
    if not bueno.any():
        return vacio

    snr = np.where(bueno, sub_d / np.sqrt(np.where(sub_v > 0, sub_v, 1.0)), np.nan)

    i_pos = int(np.nanargmax(snr))
    i_neg = int(np.nanargmin(snr))
    py, px = np.unravel_index(i_pos, snr.shape)
    ny_, nx_ = np.unravel_index(i_neg, snr.shape)

    pos_snr = float(snr[py, px])
    neg_snr = float(-snr[ny_, nx_])
    pos_xy = (float(px + x0), float(py + y0))
    neg_xy = (float(nx_ + x0), float(ny_ + y0))
    sep = float(np.hypot(pos_xy[0] - neg_xy[0], pos_xy[1] - neg_xy[1]))

    return {
        "pos_snr": pos_snr,
        "neg_snr": neg_snr,
        "pos_xy": pos_xy,
        "neg_xy": neg_xy,
        "separation_px": sep,
        "detected": bool(pos_snr > min_snr and neg_snr > min_snr
                         and 0.0 < sep <= max_separation_px),
        "n_usable": int(bueno.sum()),
    }
