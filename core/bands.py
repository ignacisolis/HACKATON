"""Las 102 bandas de SPHEREx: busqueda y metadatos.

Rol C (Ciencia). Funciones puras, sin red. El dato viene de config/bands.yaml,
que genera core/make_bands.py.

Sirve para las consideraciones C2 y C3 del enunciado: entregar las 102 bandas y
dejar que el usuario elija una. El backend y el frontend pueden usar esto para
el selector de banda sin reimplementar la grilla.

    >>> import core.bands as bd
    >>> bd.band_of_wavelength(1.4017)
    28
    >>> bd.band_info(28)["detector"]
    'D2'

El espaciado es LOGARITMICO, a poder resolvente constante: el ancho de banda
crece con la longitud de onda. Ver la cabecera de config/bands.yaml.
"""
from __future__ import annotations

import bisect
import functools
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "bands.yaml"


@functools.lru_cache(maxsize=4)
def load_config(path=None):
    p = Path(path) if path else DEFAULT_CONFIG
    if not p.is_file():
        raise FileNotFoundError(
            "No encuentro " + str(p) + ". Generalo con: python core/make_bands.py"
        )
    with p.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@functools.lru_cache(maxsize=4)
def all_bands(path=None):
    """Las 102 bandas, ordenadas por longitud de onda creciente."""
    return tuple(load_config(path)["bands"])


@functools.lru_cache(maxsize=4)
def _bordes(path=None):
    return tuple(b["wavelength_min_um"] for b in all_bands(path))


def n_bands(path=None):
    return len(all_bands(path))


def band_info(band, path=None):
    """Metadatos de una banda, por su numero de 1 a 102."""
    bandas = all_bands(path)
    if not (1 <= int(band) <= len(bandas)):
        raise KeyError("banda fuera de rango: " + str(band) + ", hay "
                       + str(len(bandas)))
    return dict(bandas[int(band) - 1])


def band_of_wavelength(wavelength_um, detector=None, path=None):
    """Numero de banda de una longitud de onda, o None si cae afuera.

    Pura.

    PASAR EL DETECTOR SIEMPRE QUE SE SEPA
    -------------------------------------
    Las 102 bandas NO son una grilla sin solapes: los detectores se solapan un
    poco en las costuras (D1 termina en 1.1167 y D2 empieza en 1.1033), asi que
    en 5 tramos angostos una misma longitud de onda cae en DOS bandas, una por
    detector. Y eso es fisicamente cierto: los dos detectores pueden medir esa
    longitud de onda.

    O sea, la banda la determina el par (detector, lambda), no lambda sola. Un
    Frame siempre sabe su detector, asi que `core.spectrum.extract()` lo pasa.

    Sin `detector`, devuelve la banda de numero mas chico que contenga esa
    longitud de onda. Es determinista, pero en las costuras puede no ser la que
    corresponde al detector que tomo el dato. `overlapping_bands()` lista los
    tramos donde pasa.
    """
    lam = float(wavelength_um)
    bandas = all_bands(path)

    if detector is not None:
        det = str(detector).replace("SPHEREx-", "")
        candidatas = [b for b in bandas if b["detector"] == det]
        if not candidatas:
            raise KeyError("detector desconocido: " + repr(detector))
        for b in candidatas:
            if b["wavelength_min_um"] <= lam < b["wavelength_max_um"]:
                return int(b["band"])
        # Borde superior del ultimo canal del detector, inclusivo.
        if abs(lam - candidatas[-1]["wavelength_max_um"]) < 1e-9:
            return int(candidatas[-1]["band"])
        return None

    # Sin detector: la primera banda que lo contenga. bisect da la ultima cuyo
    # borde inferior es <= lam, asi que hay que retroceder mientras haya solape.
    bordes = _bordes(path)
    i = bisect.bisect_right(bordes, lam) - 1
    while i > 0 and bandas[i - 1]["wavelength_max_um"] > lam:
        i -= 1
    if i < 0:
        return None
    b = bandas[i]
    if b["wavelength_min_um"] <= lam < b["wavelength_max_um"]:
        return int(b["band"])
    if i == len(bandas) - 1 and abs(lam - b["wavelength_max_um"]) < 1e-9:
        return int(b["band"])
    return None


@functools.lru_cache(maxsize=4)
def overlapping_bands(path=None):
    """Los pares de bandas que se solapan, en las costuras entre detectores.

    Pura. Devuelve una lista de dicts con las dos bandas, sus detectores y el
    tramo de longitud de onda compartido. Son 5, una por costura.

    Le importa al frontend: si el selector de banda ofrece "1.11 um" sin decir
    el detector, el usuario no sabe cual de las dos esta mirando.
    """
    bandas = all_bands(path)
    pares = []
    for i, a in enumerate(bandas):
        for b in bandas[i + 1:]:
            if b["wavelength_min_um"] >= a["wavelength_max_um"]:
                continue
            if a["detector"] == b["detector"]:
                continue
            pares.append({
                "bands": (int(a["band"]), int(b["band"])),
                "detectors": (a["detector"], b["detector"]),
                "overlap_min_um": round(b["wavelength_min_um"], 5),
                "overlap_max_um": round(a["wavelength_max_um"], 5),
                "overlap_um": round(a["wavelength_max_um"] - b["wavelength_min_um"], 5),
            })
    return tuple(pares)


def bands_of_detector(detector, path=None):
    """Numeros de banda de un detector. 'D2' -> [18..34]."""
    det = str(detector).replace("SPHEREx-", "")
    return [int(b["band"]) for b in all_bands(path) if b["detector"] == det]


def detector_of_band(band, path=None):
    return band_info(band, path)["detector"]


def summary(path=None):
    """Una fila por detector: cuantas bandas y que rango cubre."""
    cfg = load_config(path)
    por_det = {}
    for b in cfg["bands"]:
        d = por_det.setdefault(b["detector"], {
            "detector": b["detector"], "n": 0,
            "band_min": b["band"], "band_max": b["band"],
            "wavelength_min_um": b["wavelength_min_um"],
            "wavelength_max_um": b["wavelength_max_um"],
            "resolving_power": b["resolving_power"],
        })
        d["n"] += 1
        d["band_max"] = b["band"]
        d["wavelength_max_um"] = b["wavelength_max_um"]
    return [por_det[k] for k in sorted(por_det)]


if __name__ == "__main__":
    cfg = load_config()
    print("SPHEREx: " + str(cfg["n_bands"]) + " bandas, "
          + format(cfg["wavelength_min_um"], ".3f") + " a "
          + format(cfg["wavelength_max_um"], ".3f") + " um, espaciado "
          + cfg["spacing"])
    print()
    print("{:<10} {:>7} {:>9} {:>16} {:>8}".format(
        "detector", "bandas", "canales", "lambda (um)", "R"))
    print("-" * 56)
    for d in summary():
        print("{:<10} {:>7} {:>9} {:>16} {:>8}".format(
            d["detector"], str(d["band_min"]) + "-" + str(d["band_max"]), d["n"],
            format(d["wavelength_min_um"], ".3f") + "-"
            + format(d["wavelength_max_um"], ".3f"),
            d["resolving_power"]))
