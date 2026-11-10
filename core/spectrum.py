"""Extraccion y combinacion de espectros. Tarea 23, consideraciones C7 y C8.

Rol C (Ciencia). ESTADO: firmas definidas, implementacion pendiente.

Como se arma un espectro en SPHEREx
-----------------------------------
No hay "una imagen por banda". El filtro varia a lo largo del detector, asi que
en cada exposicion el objetivo cae en UNA longitud de onda. El espectro se arma
juntando muchas exposiciones: cada una aporta un punto.

Con 6 detectores x 17 canales se llega a las 102 bandas de la mision, de 0.75 a
5.01 um. Los detectores no se solapan: se encadenan.

Dos cosas que hay que tener en cuenta
-------------------------------------
1. La longitud de onda sale de `WCS-WAVE`, que el propio header declara como
   "Approximated per-pixel wavelength". Para ciencia fina IRSA recomienda el
   producto aparte Spectral WCS (CWAVE y CBAND, ~32 MB por detector). Para el
   visor alcanza la aproximacion; para un numero publicable, no.
2. La resolucion espectral NO es pareja: R ~ 35-41 en D1 a D4, pero R ~ 112 en
   D5 y ~128 en D6. Las bandas rojas son mucho mas angostas. Graficar los 102
   puntos como equivalentes da una idea falsa de la forma del espectro, asi que
   cada punto viaja con su `bandwidth_um`.
"""
from __future__ import annotations

import numpy as np

from core.datatypes import Frame, SpectrumPoint  # noqa: F401

# Apertura por defecto, en pixeles de SPHEREx (6.2 arcsec/px). 2.5 px es el
# radio que usa el propio pipeline de fotometria de Level 3 para decidir su
# aviso CONTAINS_BAD_PIXEL, asi que es un valor con respaldo.
DEFAULT_APERTURE_PX = 2.5


def extract(frames, target_key=None, ra=None, dec=None,
            aperture_px=DEFAULT_APERTURE_PX, mask_purpose="photometry",
            subtract_zodi=False):
    """Un punto de espectro por cuadro: longitud de onda y flujo en el objetivo.

    PURA: recibe Frames, devuelve una lista de SpectrumPoint. No descarga nada.

    Parametros
    ----------
    frames : lista de Frame
    target_key : str, opcional
        Clave de config/targets.yaml; propaga el movimiento propio a cada MJD.
    ra, dec : float, opcional
        Alternativa, en grados ICRS a la epoca correcta.
    aperture_px : float
        Radio de la apertura circular, en pixeles.
    mask_purpose : str
        'photometry' o 'background'. Ver core.flags.
        NO usar 'background' para medir la fuente: enmascara SOURCE y borra el
        objetivo. Medido en un recorte real de R Dra: con la mascara de
        fotometria quedan 790 de 841 pixeles usables; con la de fondo, cero.
    subtract_zodi : bool
        Si restar el modelo de luz zodiacal (`Frame.zodi`). Viene como
        referencia y NO esta restado de IMAGE.

    Devuelve
    --------
    lista de SpectrumPoint, ordenada por longitud de onda.

    Nota sobre el fondo
    -------------------
    En campos poblados puede no haber fondo local limpio dentro del recorte. En
    el recorte de R Dra que se probo, el 100 % de los pixeles tenia el flag
    SOURCE, asi que no hay anillo de cielo que medir. En esos casos el fondo hay
    que estimarlo de una apertura mas grande, o usar el modelo ZODI.
    """
    raise NotImplementedError(
        "Tarea 23. Las firmas estan fijas: el backend ya puede llamar a esto."
    )


def combine(points, n_bands=102, weighted=True):
    """Promedia los puntos que caen en la misma banda.

    PURA. Es de aca que sale la mejora de senal/ruido de la consideracion C8:
    combinar VISITAS REPETIDAS a la misma banda, no apilar los 6 detectores
    (que miden longitudes de onda distintas).

    Con 2 o 3 epocas por banda en WISE 0855, eps Ind B y RW Aur, la mejora es de
    sqrt(2) o sqrt(3). En R Dra, con ~34 epocas por banda, es de ~6.

    Parametros
    ----------
    points : lista de SpectrumPoint
    n_bands : int
        En cuantas bandas repartir el rango. 102 son las de la mision.
    weighted : bool
        Si pondera por 1/flux_err^2.

    Devuelve
    --------
    lista de SpectrumPoint con un punto por banda ocupada, con `n_pixels` como
    la suma y un campo meta con cuantas epocas entraron.
    """
    raise NotImplementedError("Tarea 23.")


def light_curve(points, band_um=None, tolerance_um=None):
    """Flujo contra tiempo para una banda, en vez de flujo contra longitud de onda.

    PURA. Es la otra mitad de lo que pide el enunciado: la meta ahora dice
    "video o series de tiempo". Para R Dra, que es una Mira de ~245 dias con 522
    dias de cobertura, esto deberia mostrar dos ciclos completos.

    Devuelve (mjds, flujos, errores), ordenado por MJD.
    """
    raise NotImplementedError("Tarea 23.")
