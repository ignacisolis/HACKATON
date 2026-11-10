"""core/ - funciones de ciencia del visor SPHEREx (rol C).

Funciones puras: reciben valores, devuelven valores. Nada de aca abre la red.
Las excepciones son los dos scripts de mantenimiento, fetch_targets.py y
fetch_coverage.py, que se corren a mano.

El Tablero nombra las tres funciones principales como core.align(),
core.subtract() y core.spectrum(), asi que se reexportan aca con ese nombre.
Las implementaciones viven en los modulos del mismo nombre.

    import core
    core.align(frames, target_key="wise_0855")
    core.subtract(frame_a, frame_b)
    core.spectrum(frames, target_key="r_dra")

Lo que ya funciona:
    core.targets   posiciones propagadas por movimiento propio (tarea 6)
    core.flags     decodificar la capa FLAGS y sus mascaras (tarea 8)

Lo que esta en firmas y falta implementar:
    core.align     tarea 21
    core.subtract  tarea 22
    core.spectrum  tarea 23
"""
from core import align as _align_mod
from core import flags, targets  # noqa: F401
from core import spectrum as _spectrum_mod
from core import subtract as _subtract_mod
from core.align import align_frames, target_pixel  # noqa: F401
from core.spectrum import combine, extract, light_curve  # noqa: F401
from core.subtract import coadd, comparable_pairs, is_comparable  # noqa: F401
from core.types import AlignedCube, Frame, SpectrumPoint  # noqa: F401

# Los nombres cortos que usa el Tablero. Ojo: esto hace que `core.subtract` y
# `core.spectrum` sean las FUNCIONES, no los modulos. Los modulos siguen
# accesibles con `from core.subtract import comparable_pairs`, que es lo que
# usa el codigo de adentro de core/.
align = _align_mod.align_frames
subtract = _subtract_mod.subtract
spectrum = _spectrum_mod.extract

__all__ = [
    "targets", "flags",
    "align", "subtract", "spectrum",
    "align_frames", "target_pixel",
    "is_comparable", "comparable_pairs", "coadd",
    "extract", "combine", "light_curve",
    "Frame", "AlignedCube", "SpectrumPoint",
]
