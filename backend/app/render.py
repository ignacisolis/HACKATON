"""Remuestreo a una grilla de cielo común (norte arriba) y render a PNG.

Por qué no core.align_frames para el video: align_frames TRASLADA cada recorte para
centrar el objetivo, pero no lo rota, y SPHEREx observa cada visita con otro ángulo
de posición. Para el video hace falta una grilla de cielo fija (norte arriba): así el
fondo queda quieto y el objetivo se mueve, que es justo lo que pide O4. Dónde cae el
objetivo en cada cuadro lo calcula core.targets (movimiento propio) y viaja en
`target_xy`. core.align_frames queda para restas y fotometría (cubos centrados).
"""
from __future__ import annotations

import io
import math

import numpy as np
from astropy.visualization import ZScaleInterval
from astropy.wcs import WCS
from PIL import Image
from scipy.ndimage import map_coordinates

from .cache import Cutout

PIXEL_ARCSEC = 6.15  # píxel de SPHEREx (OMEGA_MEDIAN ≈ 37.9 arcsec² -> ~6.15″)


def target_wcs(ra: float, dec: float, size_deg: float) -> tuple[WCS, int]:
    """Grilla TAN centrada en (ra, dec), norte arriba y este a la izquierda."""
    n = max(8, math.ceil(size_deg * 3600 / PIXEL_ARCSEC))
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [(n + 1) / 2, (n + 1) / 2]
    w.wcs.cdelt = [-PIXEL_ARCSEC / 3600, PIXEL_ARCSEC / 3600]
    return w, n


def reproject(c: Cutout, layer: np.ndarray, ra: float, dec: float, size_deg: float,
              order: int = 1) -> np.ndarray:
    """Lleva una capa del cutout a la grilla común. order=0 para FLAGS (vecino más cercano)."""
    w, n = target_wcs(ra, dec, size_deg)
    yy, xx = np.mgrid[0:n, 0:n]
    world = w.all_pix2world(np.column_stack([xx.ravel(), yy.ravel()]), 0)
    src = c.wcs.all_world2pix(world, 0)
    coords = np.vstack([src[:, 1], src[:, 0]])  # (fila, columna)
    data = layer.astype(np.float64 if order else np.int64)
    out = map_coordinates(data, coords, order=order, mode="constant", cval=np.nan if order else 0,
                          prefilter=False)
    return out.reshape(n, n)


def grid_layers(c: Cutout, ra: float, dec: float, size_deg: float, subtract_zodi: bool = False):
    """Imagen, varianza y FLAGS en la grilla de cielo común, con su WCS. Arrays con y hacia arriba.

    La varianza se interpola bilineal igual que la imagen. Eso la SOBREESTIMA un poco (la
    propagación exacta usa los pesos al cuadrado, que suman ≤ 1), así que los S/N que salen
    de acá son conservadores.
    """
    w, _ = target_wcs(ra, dec, size_deg)
    img = reproject(c, c.image - c.zodi if subtract_zodi else c.image, ra, dec, size_deg)
    var = reproject(c, c.variance, ra, dec, size_deg)
    flags = reproject(c, c.flags, ra, dec, size_deg, order=0).astype(np.uint32)
    return img, var, flags, w


def display_range(grid_img: np.ndarray) -> dict:
    """Límites que usaría el estirado, en MJy/sr, para que el frontend fije uno común al video."""
    ok = np.isfinite(grid_img)
    if ok.sum() <= 10:
        return {"zscale": None, "p99_7": None}
    lo, hi = ZScaleInterval().get_limits(grid_img[ok])
    return {"zscale": [round(float(lo), 5), round(float(hi), 5)],
            "p99_7": round(float(np.percentile(grid_img[ok], 99.7)), 5)}


def diff_png(diff: np.ndarray, vmax: float) -> bytes:
    """Escala divergente simétrica: gris medio = 0, blanco = +vmax, negro = −vmax; NaN transparente."""
    g = np.clip(np.nan_to_num(diff) / max(vmax, 1e-12), -1, 1)
    gray = (127.5 + 127.5 * g).round().astype(np.uint8)
    rgba = np.dstack([gray, gray, gray, np.where(np.isfinite(diff), 255, 0).astype(np.uint8)])
    return to_png(rgba)


def grid_xy(ra_c: float, dec_c: float, size_deg: float, ra: float, dec: float) -> list[float]:
    """Dónde cae (ra, dec) en el PNG devuelto: píxeles base 0, x a la derecha, y hacia abajo."""
    x, y = grid_array_xy(ra_c, dec_c, size_deg, ra, dec)
    _, n = target_wcs(ra_c, dec_c, size_deg)
    return [round(x, 2), round(n - 1 - y, 2)]


def grid_array_xy(ra_c: float, dec_c: float, size_deg: float, ra: float, dec: float) -> tuple[float, float]:
    """Lo mismo en coordenadas del array (y hacia arriba), que es lo que usa core/."""
    w, _ = target_wcs(ra_c, dec_c, size_deg)
    x, y = w.all_world2pix([[ra, dec]], 0)[0]
    return float(x), float(y)


STRETCHES = ("linear", "asinh")
ASINH_SOFT, ASINH_MAX = 3.0, 5.0


def stretch(img: np.ndarray, vmin: float | None = None, vmax: float | None = None,
            kind: str = "linear") -> np.ndarray:
    ok = np.isfinite(img)
    if vmin is None or vmax is None:
        lo, hi = ZScaleInterval().get_limits(img[ok]) if ok.sum() > 10 else (0.0, 1.0)
        vmin = lo if vmin is None else vmin
        vmax = hi if vmax is None else vmax
    x = (img - vmin) / max(vmax - vmin, 1e-12)
    if kind == "asinh":
        # El fondo ocupa el rango zscale y las fuentes brillantes (hasta 5x ese rango) se comprimen
        # sin quemarse. No depende de percentiles: un par de píxeles calientes no oscurece el cuadro.
        x = np.arcsinh(ASINH_SOFT * np.clip(x, 0, ASINH_MAX)) / np.arcsinh(ASINH_SOFT * ASINH_MAX)
    scaled = np.nan_to_num(np.clip(x, 0, 1))
    out = (scaled * 255).astype(np.uint8)
    out[~ok] = 0
    return out


def to_png(gray_or_rgba: np.ndarray) -> bytes:
    mode = "RGBA" if gray_or_rgba.ndim == 3 else "L"
    buf = io.BytesIO()
    # origin="lower": la fila 0 es el sur; PNG dibuja la fila 0 arriba -> se invierte
    Image.fromarray(np.ascontiguousarray(gray_or_rgba[::-1]), mode=mode).save(buf, format="PNG")
    return buf.getvalue()


def render_png(c: Cutout, ra: float, dec: float, size_deg: float, layer: str = "image",
               bits: list[int] | None = None, vmin: float | None = None,
               vmax: float | None = None, kind: str = "linear") -> bytes:
    """layer: image | image-zodi | variance | flags (máscara RGBA transparente con los bits pedidos)."""
    if layer == "flags":
        f = reproject(c, c.flags, ra, dec, size_deg, order=0)
        mask = np.zeros_like(f, dtype=bool)
        for b in bits or list(c.flag_bits.values()):
            mask |= (f & (1 << int(b))) > 0
        rgba = np.zeros((*f.shape, 4), dtype=np.uint8)
        rgba[mask] = (255, 60, 60, 150)
        return to_png(rgba)
    data = {
        "image": c.image,
        "image-zodi": c.image - c.zodi,
        "variance": c.variance,
    }.get(layer)
    if data is None:
        raise ValueError(f"capa desconocida: {layer}")
    return to_png(stretch(reproject(c, data, ra, dec, size_deg), vmin, vmax, kind))
