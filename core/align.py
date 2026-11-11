"""Alineacion de una serie de recortes sobre el objetivo. Tarea 21.

Rol C (Ciencia). Funciones puras: reciben Frames, devuelven arrays.

Por que hace falta alinear
--------------------------
Dos razones distintas, y conviene no confundirlas:

1. El objetivo tiene movimiento propio, asi que su RA/Dec cambia con la fecha.
   `core.targets.target_position()` dice donde esta en cada MJD.
2. Cada exposicion apunta distinto, asi que el mismo punto del cielo cae en un
   pixel distinto en cada recorte. Eso lo resuelve el WCS de cada recorte.

El resultado es un cubo donde el objetivo esta siempre en el mismo pixel, que es
la condicion para hacer un video, restar imagenes o sumar apertura.

Tres decisiones de implementacion, y por que
--------------------------------------------
**Los FLAGS se remuestrean por vecino mas cercano, nunca bilineal.** Interpolar
un bitmap mezcla bits de pixeles vecinos e inventa combinaciones que nunca
existieron: el promedio de SOURCE (2^21) y nada no es "medio SOURCE", es basura.

**La varianza se propaga con los pesos al cuadrado**, no se interpola como la
imagen. Si un pixel de salida es la suma w_i * v_i, su varianza es la suma
w_i^2 * var_i. Por eso el remuestreo esta escrito a mano en vez de usar
`scipy.ndimage`: asi la varianza usa exactamente los mismos pesos que la imagen,
y no una aproximacion.

Ojo con leer la varianza de mas: al interpolar baja (cuatro pesos de 0.25 dan un
cuarto de la varianza original), pero eso **no** es mejor senal/ruido. El ruido
queda correlacionado entre pixeles vecinos. Para ganar senal/ruido de verdad hay
que combinar visitas repetidas, que es `core.subtract.coadd()`.

**Los pixeles sin dato se marcan con MISSING_DATA** en la capa de flags, ademas
de quedar NaN en la imagen. Es la opcion mas segura: ese bit esta en las dos
listas de enmascarado del documento, asi que `core.flags.mask_for()` los excluye
sin que nadie tenga que acordarse.
"""
from __future__ import annotations

import numpy as np

from core import flags as fl
from core import targets as tg
from core.datatypes import AlignedCube, Frame  # noqa: F401

# Bit con el que se marcan los pixeles que quedaron sin dato tras el remuestreo.
MISSING_DATA_BIT = fl.bit_of("MISSING_DATA")
MISSING_DATA_MASK = np.uint32(1 << MISSING_DATA_BIT)


# --------------------------------------------------------------------------
# Donde cae el objetivo
# --------------------------------------------------------------------------

def target_pixel(frame, target_key=None, ra=None, dec=None):
    """Donde cae el objetivo en el recorte de `frame`, en pixeles.

    Pasar `target_key` (y lo busca en config/targets.yaml, propagando el
    movimiento propio a `frame.mjd`) o bien `ra`/`dec` en grados ya resueltos.

    Devuelve (x, y) en coordenadas de pixel del recorte, base 0 y con subpixel.
    Puede caer fuera del recorte: eso no es un error, lo decide quien llama.
    """
    if target_key is None and (ra is None or dec is None):
        raise ValueError("hace falta target_key, o bien ra y dec")
    if frame.wcs is None:
        raise ValueError("el Frame no trae WCS: sin eso no se puede alinear")
    if target_key is not None:
        ra, dec = tg.target_position(target_key, frame.mjd)
    x, y = frame.wcs.world_to_pixel_values(ra, dec)
    return float(x), float(y)


def shift_series(frames, target_key=None, ra=None, dec=None):
    """Cuanto hay que correr cada cuadro, sin remuestrear nada.

    PURA. Sirve para dos cosas:
      - decidir si vale la pena alinear: si los corrimientos son menores a ~0.1
        px, remuestrear solo agrega ruido correlacionado;
      - medir el movimiento del objetivo contra el fondo.

    Devuelve (shifts, mjds): `shifts` es (n, 2) con el corrimiento (dx, dy) que
    habria que aplicar al contenido de cada cuadro para centrar el objetivo, y
    `mjds` es (n,). Ordenado por MJD.
    """
    ordered = sorted(frames, key=lambda f: f.mjd)
    shifts, mjds = [], []
    for f in ordered:
        ny, nx = f.image.shape
        cx, cy = (nx - 1) / 2.0, (ny - 1) / 2.0
        xt, yt = target_pixel(f, target_key, ra, dec)
        shifts.append((cx - xt, cy - yt))
        mjds.append(f.mjd)
    return np.asarray(shifts, dtype=float), np.asarray(mjds, dtype=float)


# --------------------------------------------------------------------------
# Remuestreo
# --------------------------------------------------------------------------

def _bilinear_terms(xs, ys, shape):
    """Las 4 esquinas que aportan a cada pixel de salida, con su peso.

    Devuelve una lista de (iy, ix, w, dentro). Los indices vienen recortados al
    rango valido, y `dentro` dice cuales lo estaban de verdad.
    """
    ny, nx = shape
    x0 = np.floor(xs).astype(np.int64)
    y0 = np.floor(ys).astype(np.int64)
    fx = xs - x0
    fy = ys - y0
    terms = []
    for dy, dx in ((0, 0), (0, 1), (1, 0), (1, 1)):
        iy, ix = y0 + dy, x0 + dx
        w = (fy if dy else 1.0 - fy) * (fx if dx else 1.0 - fx)
        dentro = (iy >= 0) & (iy < ny) & (ix >= 0) & (ix < nx)
        terms.append((np.clip(iy, 0, ny - 1), np.clip(ix, 0, nx - 1), w, dentro))
    return terms


def _resample(frame, xs, ys):
    """Remuestrea un Frame en las coordenadas de origen (xs, ys).

    La imagen va bilineal, la varianza con los pesos al cuadrado, los flags por
    vecino mas cercano. Un pixel de salida solo vale si sus 4 esquinas con peso
    distinto de cero estaban dentro y eran finitas: asi no hay renormalizacion
    silenciosa en los bordes, solo un borde de NaN predecible.
    """
    img = np.zeros(xs.shape, dtype=float)
    var = np.zeros(xs.shape, dtype=float)
    usable = np.ones(xs.shape, dtype=bool)

    src_img = np.asarray(frame.image, dtype=float)
    src_var = np.asarray(frame.variance, dtype=float)

    for iy, ix, w, dentro in _bilinear_terms(xs, ys, src_img.shape):
        vals = src_img[iy, ix]
        vars_ = src_var[iy, ix]
        bueno = dentro & np.isfinite(vals)
        # Una esquina mala solo invalida el pixel si de verdad aportaba peso.
        usable &= bueno | (w == 0)
        img += np.where(bueno, vals * w, 0.0)
        var += np.where(bueno, np.nan_to_num(vars_) * w * w, 0.0)

    img = np.where(usable, img, np.nan)
    var = np.where(usable, var, np.nan)

    # Flags: vecino mas cercano. Interpolar un bitmap inventa bits.
    ny, nx = src_img.shape
    iyn = np.rint(ys).astype(np.int64)
    ixn = np.rint(xs).astype(np.int64)
    dentro_n = (iyn >= 0) & (iyn < ny) & (ixn >= 0) & (ixn < nx)
    flg = np.asarray(frame.flags, dtype=np.uint32)[
        np.clip(iyn, 0, ny - 1), np.clip(ixn, 0, nx - 1)
    ].copy()
    # Donde no hay dato, decirlo con el bit que las dos mascaras ya excluyen.
    sin_dato = ~usable | ~dentro_n
    flg[sin_dato] |= MISSING_DATA_MASK

    return img, var, flg, usable


# --------------------------------------------------------------------------
# La funcion principal
# --------------------------------------------------------------------------

def align_frames(frames, target_key=None, ra=None, dec=None, out_shape=None,
                 drop_if_outside=True, require_same_detector=False):
    """Recentra una serie de recortes sobre el objetivo.

    PURA: recibe Frames, devuelve un AlignedCube. No descarga nada.

    Parametros
    ----------
    frames : lista de Frame
        En cualquier orden; el resultado sale ordenado por MJD.
    target_key : str, opcional
        Clave de config/targets.yaml. Propaga el movimiento propio a cada MJD,
        que es lo que hace que WISE 0855 quede centrado en todas las fechas.
    ra, dec : float, opcional
        Alternativa a target_key, en grados ICRS, ya a la epoca correcta.
    out_shape : (ny, nx), opcional
        Forma de los cuadros de salida. Por defecto, la del recorte mas chico.
    drop_if_outside : bool
        Si el objetivo cae fuera del recorte, descarta el cuadro en vez de
        devolver uno vacio. Los descartados quedan en `AlignedCube.dropped`.
    require_same_detector : bool
        Si es True, exige que todos los cuadros sean del mismo detector y falla
        si no. Por defecto False, porque para un VIDEO mezclar detectores es
        legitimo. Para RESTAR no lo es: eso lo valida core.subtract.

    Devuelve
    --------
    AlignedCube. `center` es (x, y) donde queda el objetivo en cada cuadro, y
    `shifts_px` el corrimiento (dx, dy) que se le aplico a cada uno.

    Los pixeles sin dato quedan NaN en `cube` y con el bit MISSING_DATA prendido
    en `flags`, asi que `core.flags.mask_for()` los excluye solo.
    """
    if not frames:
        raise ValueError("no hay cuadros que alinear")
    if target_key is None and (ra is None or dec is None):
        raise ValueError("hace falta target_key, o bien ra y dec")

    if require_same_detector:
        dets = {f.detector for f in frames}
        if len(dets) > 1:
            raise ValueError(
                "se pidio un solo detector pero vinieron " + repr(sorted(dets))
                + "; cada detector mide longitudes de onda distintas"
            )

    ordered = sorted(frames, key=lambda f: f.mjd)
    if out_shape is None:
        out_shape = (min(f.image.shape[0] for f in ordered),
                     min(f.image.shape[1] for f in ordered))
    ny, nx = int(out_shape[0]), int(out_shape[1])
    if ny < 1 or nx < 1:
        raise ValueError("out_shape invalido: " + repr(out_shape))

    cx, cy = (nx - 1) / 2.0, (ny - 1) / 2.0
    yy, xx = np.mgrid[0:ny, 0:nx]
    xx = xx.astype(float)
    yy = yy.astype(float)

    imgs, vars_, flgs, mjds, dets, lams, shifts = [], [], [], [], [], [], []
    dropped = []

    for f in ordered:
        try:
            xt, yt = target_pixel(f, target_key, ra, dec)
        except Exception as exc:  # noqa: BLE001
            dropped.append({"mjd": f.mjd, "detector": f.detector,
                            "reason": "no se pudo ubicar el objetivo: " + str(exc)})
            continue

        if not (np.isfinite(xt) and np.isfinite(yt)):
            dropped.append({"mjd": f.mjd, "detector": f.detector,
                            "reason": "el WCS devolvio una posicion no finita"})
            continue

        fny, fnx = f.image.shape
        if drop_if_outside and not (0 <= xt <= fnx - 1 and 0 <= yt <= fny - 1):
            dropped.append({
                "mjd": f.mjd, "detector": f.detector,
                "reason": ("el objetivo cae fuera del recorte, en ("
                           + format(xt, ".1f") + ", " + format(yt, ".1f")
                           + ") de " + str(fnx) + "x" + str(fny)),
            })
            continue

        img, var, flg, _ = _resample(f, xx - cx + xt, yy - cy + yt)
        imgs.append(img)
        vars_.append(var)
        flgs.append(flg)
        mjds.append(f.mjd)
        dets.append(f.detector)
        lams.append(f.wavelength_um)
        shifts.append((cx - xt, cy - yt))

    if not imgs:
        return AlignedCube(
            cube=np.empty((0, ny, nx), dtype=float),
            flags=np.empty((0, ny, nx), dtype=np.uint32),
            variance=np.empty((0, ny, nx), dtype=float),
            center=(cx, cy), mjds=np.empty(0), detectors=[],
            wavelengths_um=np.empty(0), shifts_px=np.empty((0, 2)),
            dropped=dropped,
        )

    return AlignedCube(
        cube=np.stack(imgs).astype(np.float32),
        flags=np.stack(flgs).astype(np.uint32),
        variance=np.stack(vars_).astype(np.float32),
        center=(cx, cy),
        mjds=np.asarray(mjds, dtype=float),
        detectors=dets,
        wavelengths_um=np.asarray(lams, dtype=float),
        shifts_px=np.asarray(shifts, dtype=float),
        dropped=dropped,
    )


def centroid(image, center=None, box=3):
    """Centroide ponderado por flujo en una caja alrededor de `center`.

    PURA. Sirve para comprobar que la alineacion funciono, y para medir el
    movimiento propio con precision subpixel, que es como se puede mostrar el
    desplazamiento de WISE 0855 (1.35 px en toda la ventana) sin depender de que
    se vea en un video.

    Devuelve (x, y) en pixeles, o (nan, nan) si no hay flujo positivo.

    LIMITACION, medida con datos reales
    -----------------------------------
    Es un centroide ponderado por flujo, sin restar fondo ni rechazar vecinos.
    Sobre una fuente aislada da mejor que 0.1 px. Sobre el recorte real de R Dra,
    que es un campo poblado con fondo alto, se desvia 0.7 px: no porque la
    alineacion falle (el corrimiento aplicado fue exacto) sino porque el
    estimador se sesga con las fuentes vecinas.

    O sea: sirve para VERIFICAR alineacion en pruebas y para campos limpios. Para
    medir el movimiento propio de WISE 0855 en serio hace falta restar fondo y
    ajustar una PSF, que es parte de la tarea 23.
    """
    arr = np.asarray(image, dtype=float)
    ny, nx = arr.shape
    if center is None:
        center = ((nx - 1) / 2.0, (ny - 1) / 2.0)
    cx, cy = center
    x0 = max(0, int(np.floor(cx - box)))
    x1 = min(nx, int(np.ceil(cx + box)) + 1)
    y0 = max(0, int(np.floor(cy - box)))
    y1 = min(ny, int(np.ceil(cy + box)) + 1)

    sub = arr[y0:y1, x0:x1]
    w = np.where(np.isfinite(sub) & (sub > 0), sub, 0.0)
    total = w.sum()
    if total <= 0:
        return float("nan"), float("nan")
    yy, xx = np.mgrid[y0:y1, x0:x1]
    return float((w * xx).sum() / total), float((w * yy).sum() / total)
