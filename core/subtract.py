"""Resta y suma de imagenes comparables. Tarea 22, consideracion C5.

Rol C (Ciencia). ESTADO: firmas y validacion definidas, resta pendiente.

La regla que no se puede romper
------------------------------
**No se restan imagenes de distinta longitud de onda.** En SPHEREx el filtro
varia a lo largo del detector, asi que cada exposicion mide el objetivo en una
lambda concreta. Restar dos exposiciones de lambdas distintas no da "lo que
cambio en el tiempo": da la diferencia entre dos colores, que para un objeto
rojo puede ser gigante y no significa nada.

Por eso `subtract()` valida antes de operar y se niega a restar lo que no es
comparable. La validacion se puede consultar aparte con `is_comparable()`.

Para que sirve, en concreto
--------------------------
WISE 0855 se mueve solo 1.35 px entre su primera y su ultima observacion (ver
docs/ciencia.md 3.2). Eso en un video no se ve. En una resta deja un residuo en
forma de dipolo: positivo donde esta ahora, negativo donde estaba. Esa es la
forma de cumplir el objetivo O4.
"""
from __future__ import annotations

import numpy as np

from core.datatypes import Frame  # noqa: F401

# Tolerancia por defecto para considerar dos exposiciones "de la misma banda".
# Criterio: una fraccion del ancho de banda del propio cuadro. Con R ~ 40 en el
# azul el ancho es ~0.03 um a 1.2 um, y con R ~ 128 en el rojo es ~0.04 um a
# 5 um. Usar una fraccion del ancho en vez de un numero fijo evita ser
# demasiado estricto en el rojo y demasiado laxo en el azul.
MAX_DLAMBDA_FRACTION = 0.5


def is_comparable(a, b, max_dlambda_fraction=MAX_DLAMBDA_FRACTION):
    """Dice si dos cuadros se pueden restar, y por que no si no se pueden.

    PURA. Devuelve (bool, motivo). El motivo es None cuando si se pueden.

    Condiciones:
      1. Mismo detector. Detectores distintos miden rangos distintos: no se
         solapan, se encadenan (docs/ciencia.md 3.4).
      2. Longitud de onda parecida, dentro de una fraccion del ancho de banda.
      3. Misma forma de array.
    """
    if a.detector != b.detector:
        return False, ("detectores distintos: " + str(a.detector) + " vs "
                       + str(b.detector) + "; miden longitudes de onda distintas")
    if a.shape != b.shape:
        return False, ("formas distintas: " + str(a.shape) + " vs " + str(b.shape))
    dlam = abs(a.wavelength_um - b.wavelength_um)
    tol = max_dlambda_fraction * min(a.bandwidth_um, b.bandwidth_um)
    if dlam > tol:
        return False, ("diferencia de longitud de onda " + format(dlam, ".4f")
                       + " um, mayor que la tolerancia " + format(tol, ".4f") + " um")
    return True, None


def comparable_pairs(frames, max_dlambda_fraction=MAX_DLAMBDA_FRACTION):
    """Todos los pares de `frames` que se pueden restar entre si.

    PURA. Devuelve lista de (i, j) con i < j, ordenada por separacion temporal
    decreciente: los pares mas separados en el tiempo primero, que son los que
    mejor muestran el movimiento.

    Es lo que el backend necesita para ofrecerle al usuario que restar. Con 2 o 3
    epocas por banda (docs/ciencia.md 3.3) la lista va a ser corta para WISE
    0855 y eps Ind B, y larga para R Dra.
    """
    pairs = []
    for i in range(len(frames)):
        for j in range(i + 1, len(frames)):
            ok, _ = is_comparable(frames[i], frames[j], max_dlambda_fraction)
            if ok:
                pairs.append((i, j))
    pairs.sort(key=lambda p: -abs(frames[p[1]].mjd - frames[p[0]].mjd))
    return pairs


def subtract(a, b, max_dlambda_fraction=MAX_DLAMBDA_FRACTION, check=True,
             mask_purpose="photometry"):
    """Resta b de a, previa validacion. Devuelve (diferencia, varianza, mascara).

    PURA: recibe dos Frame YA ALINEADOS, devuelve arrays. Alinear es tarea de
    core.align; si se restan cuadros sin alinear, el residuo es el error de
    apuntado, no el cambio del objeto.

    Parametros
    ----------
    a, b : Frame
        Ya alineados sobre el mismo objetivo y con la misma forma.
    check : bool
        Si es False, salta la validacion. Solo para experimentar a mano; el
        backend nunca deberia pasarlo en False.
    mask_purpose : str
        Que mascara de FLAGS aplicar, 'photometry' o 'background'. Ver
        core.flags: enmascarar SOURCE borraria el objetivo.

    Devuelve
    --------
    diff : ndarray 2D
        a.image - b.image, con NaN donde cualquiera de los dos estaba enmascarado.
    var : ndarray 2D
        a.variance + b.variance.
    usable : ndarray 2D de bool
        Donde el resultado tiene sentido.

    Levanta
    -------
    ValueError
        Si los cuadros no son comparables. El mensaje dice exactamente por que.
    """
    if check:
        ok, motivo = is_comparable(a, b, max_dlambda_fraction)
        if not ok:
            raise ValueError("no se pueden restar estos cuadros: " + motivo)
    raise NotImplementedError(
        "Tarea 22. La validacion is_comparable() ya funciona y se puede usar."
    )


def coadd(frames, mask_purpose="photometry", weights=None):
    """Suma ponderada de cuadros comparables, para mejorar senal/ruido.

    PURA. Por defecto pondera por 1/varianza, que es lo optimo para ruido
    gaussiano.

    OJO con la consideracion C8 del enunciado. "Combinar los 6 detectores para
    mejorar la senal/ruido" NO puede significar apilar los 6 detectores sobre la
    misma banda: cada uno mide longitudes de onda distintas y no se solapan
    (docs/ciencia.md 3.4). La mejora sale de combinar VISITAS REPETIDAS a la
    misma banda, que es lo que hace esta funcion. Lo que aportan los 6
    detectores es extender el espectro, no profundizarlo.

    Devuelve (imagen, varianza, n_efectivo).
    """
    raise NotImplementedError("Tarea 22.")
