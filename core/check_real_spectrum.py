"""Verifica core.spectrum con datos REALES. Tarea 23, criterio de aceptacion.

Rol C (Ciencia). Script de mantenimiento: usa red y baja decenas de MB, asi que
NO corre en CI. Se corre a mano.

    python core/check_real_spectrum.py                      # WISE 0855
    python core/check_real_spectrum.py r_dra --per-det 2
    python core/check_real_spectrum.py --cache-only         # sin bajar nada nuevo

Que hace: busca observaciones del objetivo en IRSA, baja unos cuantos recortes
por detector, lee la longitud de onda en la posicion del objetivo desde
WCS-WAVE, extrae fotometria de apertura y combina por banda. Imprime el espectro
y la mejora de senal/ruido.

Ojo con WISE 0855: es una enana Y2, uno de los objetos mas frios y debiles que se
conocen. Que el flujo salga compatible con cero en varias bandas NO es un error
del codigo: es que el objeto es asi. El enunciado lo eligio justamente porque es
el caso difícil. Lo que esta prueba verifica es que la cadena completa corre
sobre datos reales y da numeros con sus barras de error, no que el objeto se
detecte.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import socket
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import certifi
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import bands as bd  # noqa: E402
from core import spectrum as sp  # noqa: E402
from core import targets as tg  # noqa: E402
from core.datatypes import Frame  # noqa: E402

IRSA_TAP = "https://irsa.ipac.caltech.edu/TAP/sync"
TIMEOUT_S = 300
CUTOUT_DEG = 0.05
DETECTORES = ["D1", "D2", "D3", "D4", "D5", "D6"]


def cache_dir():
    """Donde guardar los recortes. Fuera del repo: son datos, no codigo."""
    base = os.environ.get("SPHEREX_CACHE")
    if base:
        return Path(base)
    return Path.home() / ".cache" / "spherex-visor" / "cutouts"


def tap_csv(adql):
    socket.setdefaulttimeout(TIMEOUT_S)
    ctx = ssl.create_default_context(cafile=certifi.where())
    body = urllib.parse.urlencode({
        "REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": adql,
    }).encode()
    req = urllib.request.Request(
        IRSA_TAP, data=body, headers={"User-Agent": "spherex-visor/0.1 (hackathon)"})
    with urllib.request.urlopen(req, context=ctx) as resp:
        return list(csv.DictReader(io.StringIO(resp.read().decode())))


def buscar(target_key, por_detector):
    ra, dec = tg.target_position(target_key, "2025-11-09")
    filas = tap_csv(
        "SELECT a.uri, p.energy_bandpassname, p.time_bounds_lower "
        "FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid "
        "WHERE 1 = CONTAINS(POINT('ICRS', " + repr(ra) + ", " + repr(dec) + "), p.poly) "
        "ORDER BY p.time_bounds_lower")
    por_det = {}
    for f in filas:
        det = (f["energy_bandpassname"] or "").replace("SPHEREx-", "")
        if det in DETECTORES and len(por_det.setdefault(det, [])) < por_detector:
            por_det[det].append(f)
    return ra, dec, por_det


def bajar(uri, ra, dec, destino, intentos=5):
    """Baja un recorte, con reintentos y espera creciente.

    IRSA devuelve 503 cuando se le piden muchos recortes seguidos: pasó tras 15
    descargas consecutivas. No es un error permanente, pero hay que esperar. El
    backend va a chocar con lo mismo, asi que conviene que lo sepa.
    """
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    ctx = ssl.create_default_context(cafile=certifi.where())
    url = ("https://irsa.ipac.caltech.edu/" + uri.lstrip("/")
           + "?center=" + repr(ra) + "," + repr(dec) + "d&size=" + str(CUTOUT_DEG))
    destino.parent.mkdir(parents=True, exist_ok=True)

    import time
    for intento in range(intentos):
        req = urllib.request.Request(url, headers={"User-Agent": "spherex-visor/0.1"})
        try:
            with urllib.request.urlopen(req, context=ctx) as r:
                datos = r.read()
            destino.write_bytes(datos)
            return destino
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or intento == intentos - 1:
                raise
            espera = 2.0 * (2 ** intento)
            print("      HTTP " + str(exc.code) + ", reintento en "
                  + format(espera, ".0f") + " s", flush=True)
            time.sleep(espera)
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            if intento == intentos - 1:
                raise
            espera = 2.0 * (2 ** intento)
            print("      " + type(exc).__name__ + ", reintento en "
                  + format(espera, ".0f") + " s", flush=True)
            time.sleep(espera)
    return destino


def frame_de_fits(ruta, target_key):
    """Arma un Frame leyendo lambda y ancho de banda de WCS-WAVE."""
    import warnings
    from astropy import log
    from astropy.io import fits
    from astropy.wcs import WCS
    # astropy avisa por INFO que WCS-WAVE trae coeficientes SIP aunque su CTYPE
    # es WAVE-TAB, y los aplica igual. El sesgo medido es 0.003 um, un 9% del
    # ancho de banda: documentado en docs/ciencia.md 6.5. Aca solo molesta.
    log.setLevel("ERROR")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hdul = fits.open(ruta)
        hdr = hdul["IMAGE"].header
        wcs = WCS(hdr)
        swcs = WCS(hdr, fobj=hdul, key="W")
        mjd = float(hdr["MJD-AVG"])
        ra, dec = tg.target_position(target_key, mjd)
        x, y = wcs.world_to_pixel_values(ra, dec)
        lam, bw = swcs.pixel_to_world_values(x, y)
        det = _normalizar_detector(hdr.get("DETECTOR")) or _det_de_nombre(ruta.name)
        return Frame(
            image=hdul["IMAGE"].data.astype(float),
            flags=hdul["FLAGS"].data.astype(np.uint32),
            variance=hdul["VARIANCE"].data.astype(float),
            zodi=(hdul["ZODI"].data.astype(float) if "ZODI" in hdul else None),
            wcs=wcs, mjd=mjd, detector=det,
            wavelength_um=float(np.atleast_1d(lam)[0]),
            bandwidth_um=float(np.atleast_1d(bw)[0]),
        )


def _normalizar_detector(valor):
    """El header trae DETECTOR = 1, no D1. Normaliza a 'D1'..'D6'."""
    if valor is None:
        return None
    txt = str(valor).strip().upper().replace("SPHEREX-", "")
    if txt in DETECTORES:
        return txt
    if txt.isdigit() and ("D" + txt) in DETECTORES:
        return "D" + txt
    return None


def _det_de_nombre(nombre):
    for d in DETECTORES:
        if "_" + d + "_" in nombre or nombre.startswith(d + "_"):
            return d
    return "?"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", nargs="?", default="wise_0855")
    ap.add_argument("--per-det", type=int, default=3,
                    help="recortes por detector (cada uno ~5 MB)")
    ap.add_argument("--cache-only", action="store_true",
                    help="usa solo lo ya bajado, sin tocar la red")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    cache = cache_dir() / args.target
    rutas = []

    if args.cache_only:
        rutas = sorted(cache.glob("*.fits"))
        if not rutas:
            raise SystemExit("no hay nada en " + str(cache) + "; corre sin --cache-only")
        print("usando " + str(len(rutas)) + " recortes de " + str(cache))
    else:
        print("Buscando observaciones de " + args.target + " en IRSA...", flush=True)
        ra, dec, por_det = buscar(args.target, args.per_det)
        total = sum(len(v) for v in por_det.values())
        print("  " + str(total) + " recortes en " + str(len(por_det)) + " detectores"
              + " (~" + str(total * 5) + " MB)", flush=True)
        for det in DETECTORES:
            for k, fila in enumerate(por_det.get(det, [])):
                destino = cache / (det + "_" + str(k) + ".fits")
                nuevo = not destino.exists()
                bajar(fila["uri"], ra, dec, destino)
                rutas.append(destino)
                if nuevo:
                    print("    " + destino.name + "  "
                          + format(destino.stat().st_size / 1e6, ".1f") + " MB", flush=True)

    frames = []
    for ruta in rutas:
        f = frame_de_fits(ruta, args.target)
        if f.detector in ("?", ""):
            f.detector = _det_de_nombre(ruta.name)
        frames.append(f)

    print("\n=== puntos crudos, uno por exposicion ===")
    print("%-4s %-8s %8s %8s %6s %12s %10s %6s %s"
          % ("det", "banda", "lambda", "ancho", "px", "flujo (Jy)", "error", "SNR", "calidad"))
    puntos = sp.extract(frames, target_key=args.target)
    for p in puntos:
        snr = p.flux / p.flux_err if p.flux_err else float("nan")
        print("%-4s %-8s %8.4f %8.4f %6d %12.3e %10.2e %6.1f %s"
              % (p.detector, p.band, p.wavelength_um, p.bandwidth_um, p.n_pixels,
                 p.flux, p.flux_err, snr, p.quality))

    comb = sp.combine(puntos)
    print("\n=== espectro combinado, uno por banda ===")
    print("%-8s %-4s %8s %12s %10s %6s %8s"
          % ("banda", "det", "lambda", "flujo (Jy)", "error", "SNR", "epocas"))
    for p in comb:
        snr = p.flux / p.flux_err if p.flux_err else float("nan")
        print("%-8d %-4s %8.4f %12.3e %10.2e %6.1f %8d"
              % (p.band, p.detector, p.wavelength_um, p.flux, p.flux_err, snr, p.n_epochs))

    print("\n=== cobertura y C8 ===")
    print("  bandas distintas cubiertas: " + str(len(comb)) + " de " + str(bd.n_bands()))
    ganancias = sp.snr_gain(comb)
    multi = [g for g in ganancias if g["n_epochs"] > 1]
    print("  bandas con mas de una epoca: " + str(len(multi)))
    if multi:
        print("  mejora de senal/ruido por combinar:")
        for g in multi:
            print("    banda %-4d %s  %d epocas -> x%.2f"
                  % (g["band"], g["detector"], g["n_epochs"], g["expected_gain"]))
    else:
        print("  ninguna: con pocos recortes por detector cada exposicion cae en")
        print("  un canal distinto. Es el mismo efecto de docs/ciencia.md 6.2.")

    dudosos = [p for p in puntos if p.quality != "ok"]
    print("\n  puntos marcados dudosos: " + str(len(dudosos)) + " de " + str(len(puntos)))
    sin_fondo = [p for p in puntos if p.background is None]
    if sin_fondo:
        print("  sin fondo estimable (anillo sin pixeles limpios): " + str(len(sin_fondo)))


if __name__ == "__main__":
    main()
