"""Alineacion de una serie de recortes sobre el objetivo. Tarea 21.

Rol C (Ciencia). ESTADO: firmas definidas, implementacion pendiente.

Existe ya para que Camilo pueda escribir el backend contra una interfaz estable
sin esperar a que esto funcione. Las firmas son el contrato; si cambian, se
avisa.

Por que hace falta alinear
--------------------------
Dos razones distintas, y conviene no confundirlas:

1. El objetivo tiene movimiento propio, asi que su RA/Dec cambia con la fecha.
   `core.targets.target_position()` dice donde esta en cada MJD.
2. Cada exposicion apunta distinto, asi que el mismo punto del cielo cae en un
   pixel distinto en cada recorte. Eso lo resuelve el WCS de cada recorte.

El resultado es un cubo donde el objetivo esta siempre en el mismo pixel, que
es la condicion para hacer un video, restar imagenes o sumar apertura.
"""
from __future__ import annotations

import numpy as np

from core import targets as tg
from core.types import AlignedCube, Frame  # noqa: F401


def target_pixel(frame, target_key=None, ra=None, dec=None):
    """Donde cae el objetivo en el recorte de `frame`, en pixeles.

    Pasar `target_key` (y lo busca en config/targets.yaml, propagando el
    movimiento propio a `frame.mjd`) o bien `ra`/`dec` en grados ya resueltos.

    Devuelve (x, y) en coordenadas de pixel del recorte, con subpixel. Puede caer
    fuera del recorte: eso no es un error, lo decide quien llama.
    """
    if target_key is None and (ra is None or dec is None):
        raise ValueError("hace falta target_key, o bien ra y dec")
    if target_key is not None:
        ra, dec = tg.target_position(target_key, frame.mjd)
    x, y = frame.wcs.world_to_pixel_values(ra, dec)
    return float(x), float(y)


def align_frames(frames, target_key=None, ra=None, dec=None, out_shape=None,
                 order=1, drop_if_outside=True):
    """Recentra una serie de recortes sobre el objetivo.

    PURA: recibe Frames, devuelve un AlignedCube. No descarga nada.

    Parametros
    ----------
    frames : lista de Frame
        En cualquier orden; el resultado sale ordenado por MJD.
    target_key : str, opcional
        Clave de config/targets.yaml. Propaga el movimiento propio a cada MJD.
    ra, dec : float, opcional
        Alternativa a target_key, en grados ICRS, ya a la epoca correcta.
    out_shape : (ny, nx), opcional
        Forma de los cuadros de salida. Por defecto, la del recorte mas chico.
    order : int
        Orden de la interpolacion al remuestrear. 1 = bilineal.
    drop_if_outside : bool
        Si el objetivo cae fuera del recorte, descarta el cuadro en vez de
        devolver uno vacio. Los descartados quedan en `AlignedCube.dropped`.

    Devuelve
    --------
    AlignedCube

    Notas de implementacion
    -----------------------
    - Interpolar mezcla pixeles vecinos, y eso contamina los FLAGS. La capa de
      flags se remuestrea por vecino mas cercano, nunca bilineal, para no
      inventar bits que no estaban.
    - La varianza no se interpola como la imagen: hay que propagarla. Con orden
      1 la aproximacion razonable es remuestrear la varianza con los cuadrados
      de los pesos.
    - No mezclar detectores en un mismo cubo sin pensarlo: cada uno mide otra
      longitud de onda. Ver core.subtract.comparable_pairs().
    """
    raise NotImplementedError(
        "Tarea 21. Las firmas estan fijas: el backend ya puede llamar a esto."
    )


def shift_series(frames, target_key=None, ra=None, dec=None):
    """Cuanto hay que correr cada cuadro, sin remuestrear nada.

    Util para dos cosas antes de que align_frames() exista:
      - decidir si vale la pena alinear (si los corrimientos son < 0.1 px, no);
      - medir el movimiento propio del objetivo contra el fondo.

    Devuelve un array (n_frames, 2) con los corrimientos en pixeles, y la lista
    de MJD correspondiente.
    """
    raise NotImplementedError("Tarea 21.")
