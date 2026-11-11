"""Tipos de intercambio entre core/ y backend/.

Rol C (Ciencia). Esto es el contrato: lo que `core/` recibe y lo que devuelve.
Son contenedores de arrays, sin logica y sin red. Si cambia algo de aca, hay que
avisar a Camilo, porque es la frontera entre las dos carpetas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class Frame:
    """Una exposicion recortada, con todo lo que core/ necesita para operar.

    El backend arma esto a partir de un cutout de IRSA. core/ nunca lo descarga.

    Un recorte de SPHEREx viene como FITS MEF; las extensiones que usamos son
    IMAGE, FLAGS, VARIANCE y, opcionalmente, ZODI. La PSF NO se incluye: viene
    sin recortar (~4.9 MB) y es ~99 % del peso de un cutout.
    """

    image: np.ndarray          # 2D float32, MJy/sr (extension IMAGE)
    flags: np.ndarray          # 2D int32/uint32, bitmap (extension FLAGS)
    variance: np.ndarray       # 2D float32 (extension VARIANCE)
    wcs: Any                   # astropy.wcs.WCS espacial del recorte
    mjd: float                 # MJD-AVG del header: el punto medio de la toma
    detector: str              # 'D1' .. 'D6'
    wavelength_um: float       # lambda EN LA POSICION DEL OBJETIVO, no del recorte
    bandwidth_um: float        # ancho de banda en esa posicion
    zodi: np.ndarray | None = None   # modelo de luz zodiacal; NO esta restado
    release: str | None = None       # p.ej. 'l2b-v20-2025-251', para C1
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.image.shape != self.flags.shape:
            raise ValueError(
                "image y flags tienen que tener la misma forma: "
                + str(self.image.shape) + " vs " + str(self.flags.shape)
            )
        if self.image.shape != self.variance.shape:
            raise ValueError(
                "image y variance tienen que tener la misma forma: "
                + str(self.image.shape) + " vs " + str(self.variance.shape)
            )

    @property
    def shape(self):
        return self.image.shape


@dataclass
class AlignedCube:
    """Serie de recortes recentrados sobre el objetivo, lista para video o resta.

    `cube[i]` es el cuadro i ya alineado. Todos los cuadros comparten la misma
    forma y el objetivo cae siempre en `center`.
    """

    cube: np.ndarray           # 3D (n_frames, ny, nx), float32
    flags: np.ndarray          # 3D, mismo shape
    variance: np.ndarray       # 3D, mismo shape
    center: tuple              # (x, y) donde queda el objetivo en cada cuadro
    mjds: np.ndarray           # 1D (n_frames,) MJD de cada cuadro
    detectors: list            # (n_frames,) 'D1'..'D6'
    wavelengths_um: np.ndarray  # 1D (n_frames,) lambda en el objetivo
    shifts_px: np.ndarray      # 2D (n_frames, 2) corrimiento aplicado a cada cuadro
    # Ancho de banda de cada cuadro. Hace falta para decidir que cuadros son
    # comparables sin volver a los Frame de origen: la tolerancia de la resta es
    # una fraccion del ancho de banda, no un numero fijo.
    bandwidths_um: np.ndarray = None
    # Como se alineo el cubo. Cambia por completo lo que significa una resta:
    #   'target'  el objetivo esta fijo y el fondo se mueve  -> para apilar
    #   'sky'     el fondo esta fijo y el objetivo se mueve   -> para restar
    aligned_on: str = "target"
    dropped: list = field(default_factory=list)  # cuadros descartados y por que

    def __len__(self):
        return 0 if self.cube is None else len(self.cube)


@dataclass
class SpectrumPoint:
    """Una medicion de flujo a una longitud de onda, en una fecha."""

    wavelength_um: float
    bandwidth_um: float
    flux: float                # MJy/sr, o Jy si se integra apertura
    flux_err: float
    mjd: float
    detector: str
    n_pixels: int              # pixeles que entraron en la apertura
    flagged_fraction: float    # cuantos de la apertura estaban enmascarados
    quality: str = "ok"        # 'ok' | 'suspect' | 'bad'
