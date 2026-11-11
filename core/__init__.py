"""core/ - funciones de ciencia del visor SPHEREx (rol C).

Funciones puras: reciben valores, devuelven valores. Nada de aca abre la red.
Las excepciones son los tres scripts de mantenimiento, fetch_targets.py,
fetch_coverage.py y el notebook de Fase 0, que se corren a mano.

Nombres
-------
El Tablero nombra las tres funciones principales como core.align(),
core.subtract() y core.spectrum(). NO se exponen asi: eso haria que
`core.align` fuera la funcion y no el modulo, y entonces
`from core import align` devolveria algo distinto a lo que cualquiera espera.
Es un error que no avisa y cuesta un rato encontrar. El mapeo real es:

    Tablero            de verdad
    core.align()    -> core.align_frames(frames, target_key=...)
    core.subtract() -> core.subtract_frames(a, b)
    core.spectrum() -> core.extract_spectrum(frames, target_key=...)

Los modulos siguen siendo modulos: `core.align`, `core.subtract`,
`core.spectrum`, `core.targets`, `core.flags`, `core.datatypes`.

Y los tipos de intercambio viven en `core.datatypes`, NO en `core.types`: ese
nombre le hace sombra al modulo `types` de la biblioteca estandar. Localmente
pasaba porque el interprete ya tiene `types` cargado al arrancar; en Linux el CI
rompia con "cannot import name GenericAlias from partially initialized module
types". El CI ahora comprueba que ningun modulo de core/ se llame como uno de la
stdlib.

Estado
------
Listo:
    core.targets        posiciones propagadas por movimiento propio (tarea 6)
    core.flags          decodificar la capa FLAGS y sus mascaras (tarea 8)
    core.align          alineacion por WCS con movimiento propio (tarea 21)
Firmas, sin implementar:
    core.subtract       tarea 22 (la validacion is_comparable() ya funciona)
    core.spectrum       tarea 23
"""
from core import align, datatypes, flags, spectrum, subtract, targets  # noqa: F401
from core.align import align_frames, centroid, shift_series, target_pixel  # noqa: F401
from core.flags import bit_counts, decode, good_pixels, mask_for  # noqa: F401
from core.spectrum import combine, light_curve  # noqa: F401
from core.spectrum import extract as extract_spectrum  # noqa: F401
from core.subtract import coadd, comparable_pairs, is_comparable  # noqa: F401
from core.subtract import subtract as subtract_frames  # noqa: F401
from core.targets import needs_pm_correction, target_position, target_skycoord  # noqa: F401
from core.datatypes import AlignedCube, Frame, SpectrumPoint  # noqa: F401

__all__ = [
    # modulos
    "align", "datatypes", "flags", "spectrum", "subtract", "targets",
    # tarea 6
    "target_position", "target_skycoord", "needs_pm_correction",
    # tarea 8
    "decode", "mask_for", "good_pixels", "bit_counts",
    # tarea 21
    "align_frames", "target_pixel", "shift_series", "centroid",
    # tarea 22
    "subtract_frames", "is_comparable", "comparable_pairs", "coadd",
    # tarea 23
    "extract_spectrum", "combine", "light_curve",
    # tipos de intercambio
    "Frame", "AlignedCube", "SpectrumPoint",
]
