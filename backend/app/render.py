"""Remuestreo a una grilla común (norte arriba) y render a PNG.

PROVISIONAL: la alineación "de verdad" (con movimiento propio) es core.align() de Nacho.
Esto solo deja todas las exposiciones en la misma grilla para que el video no rote.
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


def stretch(img: np.ndarray, vmin: float | None = None, vmax: float | None = None) -> np.ndarray:
    ok = np.isfinite(img)
    if vmin is None or vmax is None:
        lo, hi = ZScaleInterval().get_limits(img[ok]) if ok.sum() > 10 else (0.0, 1.0)
        vmin = lo if vmin is None else vmin
        vmax = hi if vmax is None else vmax
    scaled = np.nan_to_num(np.clip((img - vmin) / max(vmax - vmin, 1e-12), 0, 1))
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
               vmax: float | None = None) -> bytes:
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
    return to_png(stretch(reproject(c, data, ra, dec, size_deg), vmin, vmax))
