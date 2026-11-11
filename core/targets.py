"""Posiciones de los objetivos, propagadas a la fecha de cada observacion.

Rol C (Ciencia). Funciones puras: reciben valores, devuelven valores. No tocan
la red ni escriben archivos. El backend las llama; nadie mas habla con SIMBAD.

El dato de entrada es config/targets.yaml, que genera core/fetch_targets.py.

Para que sirve
--------------
Las coordenadas de catalogo estan a epoca J2000.0. SPHEREx observa en 2025-2026.
Un objeto con movimiento propio alto se corrio entre una fecha y la otra, y con
pixeles de 6.2 arcsec ese corrimiento llega a decenas de pixeles. Antes de
recortar una imagen hay que preguntar donde estaba el objeto ESE dia:

    >>> import core.targets as t
    >>> t.target_position("wise_0855", 60800.0)      # MJD del header FITS
    (133.76..., -7.242...)

Y para alinear una serie de epocas (tarea 21):

    >>> ra, dec = t.target_position("wise_0855", mjd_de_la_exposicion)
    >>> x, y = wcs.world_to_pixel(SkyCoord(ra, dec, unit="deg"))
"""
from __future__ import annotations

import functools
from pathlib import Path

import numpy as np
import yaml
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time

# config/ esta al lado de core/, en la raiz del repo.
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "targets.yaml"

# Escala de placa de SPHEREx. Se usa solo para expresar separaciones en pixeles.
SPHEREX_PIX_ARCSEC = 6.2


# --------------------------------------------------------------------------
# Carga de configuracion
# --------------------------------------------------------------------------

@functools.lru_cache(maxsize=4)
def load_config(path=None):
    """Lee targets.yaml. Cacheado: el archivo no cambia mientras corre el proceso."""
    p = Path(path) if path else DEFAULT_CONFIG
    if not p.is_file():
        raise FileNotFoundError(
            "No encuentro " + str(p) + ". Generalo con: python core/fetch_targets.py"
        )
    with p.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def target_keys(path=None):
    """Claves de los objetivos de la demo, en orden."""
    return list(load_config(path)["targets"].keys())


def get_target(key, path=None):
    """Bloque completo de un objetivo (o de un objeto de contexto)."""
    cfg = load_config(path)
    if key in cfg["targets"]:
        return cfg["targets"][key]
    if key in cfg.get("context", {}):
        return cfg["context"][key]
    raise KeyError(
        "Objetivo desconocido: " + repr(key) + ". Conocidos: " + repr(target_keys(path))
    )


# --------------------------------------------------------------------------
# Propagacion de movimiento propio: la parte pura
# --------------------------------------------------------------------------

def as_time(when):
    """Normaliza una fecha a astropy.Time.

    Acepta:
      - astropy.Time, tal cual
      - numero: se interpreta como MJD, que es lo que traen los headers FITS
      - texto: cualquier cosa que entienda astropy ('2026-05-14', 'J2000.0')
    """
    if isinstance(when, Time):
        return when
    if isinstance(when, (int, float, np.integer, np.floating)):
        return Time(float(when), format="mjd")
    return Time(str(when))


def propagate(ra_deg, dec_deg, pm_ra_cosdec_mas_yr, pm_dec_mas_yr, to_epoch,
              from_epoch="J2000.0", distance_pc=None, radial_velocity_km_s=None):
    """Mueve una posicion de `from_epoch` a `to_epoch` por movimiento propio.

    Pura: no lee configuracion ni archivos. Escalares o arrays de numpy.

    pm_ra_cosdec ya incluye el factor cos(dec), que es como lo publica SIMBAD
    y Gaia. `distance_pc` y `radial_velocity_km_s` son opcionales: solo cambian
    el resultado por aceleracion de perspectiva, que para nuestros objetivos es
    muy por debajo de un pixel. Se pasan cuando se conocen porque no cuestan.

    Devuelve (ra_deg, dec_deg) en ICRS a la epoca pedida.
    """
    kw = dict(
        ra=np.asarray(ra_deg, dtype=float) * u.deg,
        dec=np.asarray(dec_deg, dtype=float) * u.deg,
        pm_ra_cosdec=np.asarray(pm_ra_cosdec_mas_yr, dtype=float) * u.mas / u.yr,
        pm_dec=np.asarray(pm_dec_mas_yr, dtype=float) * u.mas / u.yr,
        frame="icrs",
        obstime=as_time(from_epoch),
    )
    if distance_pc:
        kw["distance"] = float(distance_pc) * u.pc
        # radial_velocity sin distance no aporta nada, por eso va anidado.
        if radial_velocity_km_s is not None:
            kw["radial_velocity"] = float(radial_velocity_km_s) * u.km / u.s

    moved = SkyCoord(**kw).apply_space_motion(new_obstime=as_time(to_epoch))
    return float(moved.ra.deg), float(moved.dec.deg)


def target_position(key, when, path=None):
    """Donde apuntar para `key` en la fecha `when`.

    `when` suele ser el MJD de la exposicion, sacado del header FITS.
    Devuelve (ra_deg, dec_deg) en ICRS.
    """
    tgt = get_target(key, path)
    a = tgt["astrometry"]
    return propagate(
        a["ra_deg"], a["dec_deg"],
        a["pm_ra_cosdec_mas_yr"], a["pm_dec_mas_yr"],
        to_epoch=when,
        from_epoch=a["coord_epoch"],
        distance_pc=a.get("distance_pc"),
        radial_velocity_km_s=a.get("radial_velocity_km_s"),
    )


def target_skycoord(key, when, path=None):
    """Igual que target_position pero devuelve SkyCoord, listo para el WCS."""
    ra, dec = target_position(key, when, path)
    return SkyCoord(ra * u.deg, dec * u.deg, frame="icrs")


def needs_pm_correction(key, path=None):
    """True si ignorar el movimiento propio desplaza mas de medio pixel."""
    return get_target(key, path)["pm_correction"] == "required"


# --------------------------------------------------------------------------
# Utilidades de comparacion
# --------------------------------------------------------------------------

def separation_arcsec(ra1, dec1, ra2, dec2):
    """Separacion angular entre dos posiciones, en arcsec. Pura."""
    a = SkyCoord(ra1 * u.deg, dec1 * u.deg, frame="icrs")
    b = SkyCoord(ra2 * u.deg, dec2 * u.deg, frame="icrs")
    return float(a.separation(b).to_value(u.arcsec))


def separation_px(ra1, dec1, ra2, dec2, pix_arcsec=SPHEREX_PIX_ARCSEC):
    """Lo mismo en pixeles de SPHEREx."""
    return separation_arcsec(ra1, dec1, ra2, dec2) / pix_arcsec


def drift_between(key, start, end, path=None):
    """Cuanto se corre un objetivo entre dos fechas, en arcsec y pixeles."""
    ra0, dec0 = target_position(key, start, path)
    ra1, dec1 = target_position(key, end, path)
    arcsec = separation_arcsec(ra0, dec0, ra1, dec1)
    return arcsec, arcsec / SPHEREX_PIX_ARCSEC


def summary_rows(path=None):
    """Tabla resumida de los objetivos, para docs y para la presentacion."""
    cfg = load_config(path)
    rows = []
    for key, tgt in cfg["targets"].items():
        a, p = tgt["astrometry"], tgt["positions"]
        rows.append({
            "key": key,
            "label": tgt["label"],
            "simbad_id": tgt["simbad_id"],
            "otype": tgt["otype"],
            "ra_j2000": a["ra_deg"],
            "dec_j2000": a["dec_deg"],
            "pm_arcsec_yr": a["pm_total_arcsec_yr"],
            "distance_pc": a["distance_pc"],
            "drift_px": p["spherex_end"]["drift_from_j2000_px"],
            "pm_correction": tgt["pm_correction"],
        })
    return rows


if __name__ == "__main__":
    # Resumen rapido por consola.
    hdr = ("objetivo", "SIMBAD", "pm as/ano", "dist pc", "corr. px", "correccion")
    print("{:<12} {:<26} {:>10} {:>8} {:>9}  {}".format(*hdr))
    print("-" * 82)
    for r in summary_rows():
        print("{:<12} {:<26} {:>10.4f} {:>8} {:>9.2f}  {}".format(
            r["key"], r["simbad_id"], r["pm_arcsec_yr"],
            r["distance_pc"], r["drift_px"], r["pm_correction"],
        ))
