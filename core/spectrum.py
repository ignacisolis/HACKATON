"""Extraccion y combinacion de espectros. Tarea 23, consideraciones C7 y C8.

Rol C (Ciencia). Funciones puras: reciben Frames, devuelven mediciones.

Como se arma un espectro en SPHEREx
-----------------------------------
No hay "una imagen por banda". El filtro varia a lo largo del detector, asi que
en cada exposicion el objetivo cae en UNA longitud de onda. El espectro se arma
juntando muchas exposiciones: cada una aporta un punto.

Esto se verifico con datos reales: 6 exposiciones consecutivas de D2 sobre R Dra
cayeron en las bandas 28, 29, 30, 31, 32 y 33, o sea una por canal, consecutivas.
SPHEREx va corriendo el canal entre exposiciones.

Tres cosas que hay que tener en cuenta
--------------------------------------
1. La longitud de onda sale de `WCS-WAVE`, que el propio header declara como
   "Approximated per-pixel wavelength". Medido, el sesgo por la ambiguedad del
   SIP es de 0.003 um, un 9% del ancho de banda. Para el visor alcanza; para un
   numero publicable hay que usar el producto aparte Spectral WCS (CWAVE y
   CBAND), como recomienda IRSA.
2. La resolucion espectral NO es pareja: R ~ 35-41 en D1 a D4, pero R ~ 112 en
   D5 y ~128 en D6. Las bandas rojas son mucho mas angostas, asi que cada punto
   viaja con su `bandwidth_um` y graficarlos como equivalentes miente.
3. **No enmascarar SOURCE al medir la fuente.** Es la mascara de fuentes y marca
   justamente los pixeles del objetivo. Medido en un recorte real de R Dra: con
   la mascara de fotometria quedan 790 de 841 pixeles usables; con la de fondo,
   cero.

Unidades
--------
`IMAGE` viene en MJy/sr, que es brillo superficial. `extract()` devuelve flujo
integrado en **Jy**, multiplicando por el angulo solido del pixel que sale del
propio WCS. El brillo superficial medio queda en `surface_brightness`.
"""
from __future__ import annotations

import math

import numpy as np

from core import bands as bd
from core import flags as fl
from core import targets as tg
from core.datatypes import Frame, SpectrumPoint  # noqa: F401

# Apertura por defecto, en pixeles de SPHEREx (6.2 arcsec/px). 2.5 px es el
# radio que usa el propio pipeline de Level 3 para decidir su aviso
# CONTAINS_BAD_PIXEL, asi que es un valor con respaldo.
DEFAULT_APERTURE_PX = 2.5

# Anillo de fondo, en unidades del radio de apertura.
BG_IN = 2.0
BG_OUT = 3.0
# Minimo de pixeles limpios en el anillo para confiar en el fondo.
BG_MIN_PIXELS = 8

DEG2_TO_SR = (math.pi / 180.0) ** 2


def _pixel_solid_angle_sr(wcs):
    """Angulo solido de un pixel, en estereorradianes, desde el WCS."""
    try:
        from astropy.wcs.utils import proj_plane_pixel_area
        return float(proj_plane_pixel_area(wcs.celestial)) * DEG2_TO_SR
    except Exception:  # noqa: BLE001
        # Sin WCS utilizable, caer a la escala nominal de SPHEREx.
        return (6.2 / 3600.0) ** 2 * DEG2_TO_SR


def _mascara_circular(shape, cx, cy, r_in, r_out=None):
    """True dentro de un circulo de radio r_in, o de un anillo si hay r_out."""
    ny, nx = shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    d2 = (xx - cx) ** 2 + (yy - cy) ** 2
    if r_out is None:
        return d2 <= r_in ** 2
    return (d2 >= r_in ** 2) & (d2 <= r_out ** 2)


def extract(frames, target_key=None, ra=None, dec=None,
            aperture_px=DEFAULT_APERTURE_PX, mask_purpose="photometry",
            subtract_background=True, subtract_zodi=False):
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
        'photometry' o 'background'. NO usar 'background' para medir la fuente.
    subtract_background : bool
        Estima el fondo en un anillo y lo resta. Si el anillo no tiene al menos
        BG_MIN_PIXELS limpios, NO inventa un cero: deja background en None y
        marca el punto como 'suspect'.
    subtract_zodi : bool
        Resta el modelo de luz zodiacal (`Frame.zodi`), que viene como
        referencia y NO esta restado de IMAGE.

    Devuelve
    --------
    lista de SpectrumPoint, ordenada por longitud de onda.

    Limitacion
    ----------
    Es fotometria de apertura con pixeles enteros: entra el pixel cuyo centro
    cae dentro del circulo. Con un radio de 2.5 px eso deja un error de
    cuantizacion de unos pocos por ciento. El pipeline de IRSA ajusta una PSF
    (con Tractor) justamente por eso. Para el visor alcanza; para precision
    fotometrica hay que ajustar PSF.
    """
    if target_key is None and (ra is None or dec is None):
        raise ValueError("hace falta target_key, o bien ra y dec")

    puntos = []
    for f in frames:
        if f.wcs is None:
            continue
        if target_key is not None:
            t_ra, t_dec = tg.target_position(target_key, f.mjd)
        else:
            t_ra, t_dec = ra, dec
        cx, cy = f.wcs.world_to_pixel_values(t_ra, t_dec)
        cx, cy = float(cx), float(cy)
        if not (np.isfinite(cx) and np.isfinite(cy)):
            continue

        img = np.asarray(f.image, dtype=float)
        var = np.asarray(f.variance, dtype=float)
        if subtract_zodi and f.zodi is not None:
            img = img - np.asarray(f.zodi, dtype=float)

        malos = fl.mask_for(f.flags, mask_purpose)
        finito = np.isfinite(img) & np.isfinite(var)

        apertura = _mascara_circular(img.shape, cx, cy, aperture_px)
        usable = apertura & finito & ~malos
        n_ap = int(apertura.sum())
        n_usable = int(usable.sum())
        if n_ap == 0 or n_usable == 0:
            continue

        # Fondo en un anillo, con la mascara de FONDO: ahi si hay que sacar
        # SOURCE, porque se busca cielo limpio.
        fondo = None
        anillo = _mascara_circular(img.shape, cx, cy,
                                   BG_IN * aperture_px, BG_OUT * aperture_px)
        anillo_limpio = anillo & finito & ~fl.mask_for(f.flags, "background")
        if subtract_background:
            if int(anillo_limpio.sum()) >= BG_MIN_PIXELS:
                fondo = float(np.median(img[anillo_limpio]))
            # Si no alcanza, fondo queda None: no se inventa un cero.

        valores = img[usable] - (fondo if fondo is not None else 0.0)
        omega = _pixel_solid_angle_sr(f.wcs)
        # MJy/sr * sr * 1e6 Jy/MJy = Jy
        escala = omega * 1e6
        flujo = float(valores.sum()) * escala
        # Varianza en (MJy/sr)^2; el error del fondo se desprecia frente al del
        # pixel porque la mediana del anillo usa muchos mas pixeles.
        err = float(np.sqrt(np.nansum(var[usable]))) * escala

        fraccion_marcada = 1.0 - n_usable / n_ap
        if fondo is None and subtract_background:
            calidad = "suspect"
        elif fraccion_marcada > 0.5:
            calidad = "suspect"
        else:
            calidad = "ok"

        puntos.append(SpectrumPoint(
            wavelength_um=float(f.wavelength_um),
            bandwidth_um=float(f.bandwidth_um),
            flux=flujo, flux_err=err, mjd=float(f.mjd), detector=f.detector,
            n_pixels=n_usable, flagged_fraction=fraccion_marcada,
            quality=calidad, unit="Jy", background=fondo,
            surface_brightness=float(valores.mean()),
            band=bd.band_of_wavelength(f.wavelength_um, f.detector),
        ))

    puntos.sort(key=lambda p: p.wavelength_um)
    return puntos


def combine(points, weighted=True):
    """Promedia los puntos que caen en la misma banda de las 102.

    PURA. De aca sale la mejora de senal/ruido de la consideracion C8:
    combinar VISITAS REPETIDAS a la misma banda, no apilar los 6 detectores,
    que miden longitudes de onda distintas y no se solapan.

    Con 2 o 3 epocas por banda en WISE 0855, eps Ind B y RW Aur, la mejora es de
    sqrt(2) o sqrt(3). En R Dra, con ~34 epocas por banda, es de ~6.

    La banda la asigna `core.bands`, con la grilla logaritmica de R constante.
    Los puntos cuya longitud de onda cae fuera de las 102 bandas se descartan.

    Devuelve una lista de SpectrumPoint, una por banda ocupada, ordenada por
    longitud de onda. `n_epochs` dice cuantos puntos entraron, y
    `wavelength_um` es el centro de la banda, no el promedio de los puntos.
    """
    por_banda = {}
    for p in points:
        banda = p.band if p.band is not None else bd.band_of_wavelength(
            p.wavelength_um, p.detector)
        if banda is None:
            continue
        por_banda.setdefault(int(banda), []).append(p)

    salida = []
    for banda in sorted(por_banda):
        grupo = por_banda[banda]
        info = bd.band_info(banda)
        flujos = np.array([p.flux for p in grupo], dtype=float)
        errores = np.array([p.flux_err for p in grupo], dtype=float)
        bueno = np.isfinite(flujos) & np.isfinite(errores) & (errores > 0)
        if not bueno.any():
            continue

        if weighted:
            w = np.zeros_like(errores)
            w[bueno] = 1.0 / errores[bueno] ** 2
            total = w.sum()
            flujo = float((flujos * w)[bueno].sum() / total)
            err = float(math.sqrt(1.0 / total))
        else:
            flujo = float(flujos[bueno].mean())
            err = float(errores[bueno].mean() / math.sqrt(int(bueno.sum())))

        malos = [p for p in grupo if p.quality != "ok"]
        salida.append(SpectrumPoint(
            wavelength_um=info["wavelength_um"],
            bandwidth_um=info["bandwidth_um"],
            flux=flujo, flux_err=err,
            mjd=float(np.mean([p.mjd for p in grupo])),
            detector=info["detector"],
            n_pixels=int(sum(p.n_pixels for p in grupo)),
            flagged_fraction=float(np.mean([p.flagged_fraction for p in grupo])),
            quality="suspect" if len(malos) > len(grupo) / 2 else "ok",
            unit=grupo[0].unit, band=banda,
            n_epochs=int(bueno.sum()),
        ))
    return salida


def light_curve(points, band=None, detector=None):
    """Flujo contra tiempo, en vez de flujo contra longitud de onda.

    PURA. Es la otra mitad de lo que pide el enunciado: la meta dice "video o
    series de tiempo". Para R Dra, una Mira de ~245 dias con 522 dias de
    cobertura, esto deberia mostrar dos ciclos completos.

    `band` filtra por numero de banda (1 a 102) y `detector` por detector. Sin
    filtros mezcla todas las longitudes de onda, lo que casi nunca es lo que se
    quiere: un objeto rojo parecera variar solo por cambiar de banda. Si no se
    pasa ninguno, avisa con un ValueError.

    Devuelve (mjds, flujos, errores), ordenado por MJD.
    """
    if band is None and detector is None:
        raise ValueError(
            "hace falta band o detector: mezclar longitudes de onda en una curva "
            "de luz hace que un objeto rojo parezca variar solo por cambiar de "
            "banda. Pasa band=<1..102> o detector='D2'."
        )
    sel = []
    for p in points:
        b = p.band if p.band is not None else bd.band_of_wavelength(
            p.wavelength_um, p.detector)
        if band is not None and b != int(band):
            continue
        if detector is not None and p.detector != str(detector).replace("SPHEREx-", ""):
            continue
        sel.append(p)
    sel.sort(key=lambda p: p.mjd)
    return (np.array([p.mjd for p in sel], dtype=float),
            np.array([p.flux for p in sel], dtype=float),
            np.array([p.flux_err for p in sel], dtype=float))


def snr_gain(combined_points):
    """Cuanto mejoro la senal/ruido al combinar, banda por banda.

    PURA. Devuelve una lista de dicts con la banda, cuantas epocas entraron y la
    mejora esperada sqrt(n). Sirve para mostrar la consideracion C8 en el pitch
    con numeros en vez de con una promesa.
    """
    return [{
        "band": p.band, "detector": p.detector,
        "wavelength_um": p.wavelength_um,
        "n_epochs": p.n_epochs,
        "expected_gain": round(math.sqrt(p.n_epochs), 2) if p.n_epochs else 0.0,
    } for p in combined_points]
