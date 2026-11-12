"""Valida los 4 objetivos del enunciado con datos REALES. Tarea 27, mitad cientifica.

Rol C (Ciencia). Script de mantenimiento: usa red y baja decenas de MB, asi que
NO corre en CI.

    python core/validate_targets.py                 # los 4
    python core/validate_targets.py rw_aur r_dra
    python core/validate_targets.py --cache-only

La tarea 27 pide dos cosas: validar los 4 casos y dejar un link permanente por
objeto. Los links dependen de que la web este desplegada (tareas 13 y 16). Esto
hace la otra mitad: comprobar, con recortes de verdad, que lo que el enunciado
pide de cada objetivo se puede demostrar con `core/`.

Que se le pide a cada uno, segun el enunciado:

    eps Ind B   par de enanas cafes orbitando una estrella -> ver la zona del
                sistema sin que la estrella A contamine la medicion
    WISE 0855   movimiento propio muy alto -> ver el desplazamiento
    RW Aur      estrella variable -> ver el cambio de brillo
    R Dra       variable evolucionada -> ver brillo y espectro
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astropy.time import Time  # noqa: E402

from core import align as al  # noqa: E402
from core import spectrum as sp  # noqa: E402
from core import subtract as sb  # noqa: E402
from core import targets as tg  # noqa: E402
from core.check_real_spectrum import (  # noqa: E402
    DETECTORES, _det_de_nombre, bajar, buscar, cache_dir, frame_de_fits, tap_csv,
)

# Que detector usar para la serie temporal de cada objetivo, y cuantas fechas.
# Para R Dra se usa D1, que es donde tiene mas cobertura (584 obs, 113 fechas).
SERIE = {
    "eps_ind_b": ("D2", 6),
    "wise_0855": ("D2", 6),
    "rw_aur": ("D2", 8),
    "r_dra": ("D1", 8),
}


def fecha_de(fila):
    return Time(float(fila["time_bounds_lower"]), format="mjd").isot[:10]


def elegir_serie(filas, detector, n):
    """n exposiciones del detector pedido, en fechas distintas y bien repartidas."""
    del_det = [f for f in filas
               if (f["energy_bandpassname"] or "").endswith(detector)]
    por_fecha = {}
    for f in del_det:
        por_fecha.setdefault(fecha_de(f), f)
    fechas = sorted(por_fecha)
    if not fechas:
        return []
    if len(fechas) <= n:
        elegidas = fechas
    else:
        idx = np.linspace(0, len(fechas) - 1, n).round().astype(int)
        elegidas = [fechas[i] for i in dict.fromkeys(idx.tolist())]
    return [por_fecha[d] for d in elegidas]


def elegir_espectro(filas):
    """Una exposicion por detector, para cubrir 0.75 a 5 um."""
    out = []
    vistos = set()
    for f in filas:
        det = (f["energy_bandpassname"] or "").replace("SPHEREx-", "")
        if det in DETECTORES and det not in vistos:
            vistos.add(det)
            out.append(f)
    return out


def cargar(target_key, solo_cache=False):
    """Devuelve (frames_espectro, frames_serie, detector_serie)."""
    cache = cache_dir() / ("val_" + target_key)
    det_serie, n_serie = SERIE[target_key]

    if solo_cache:
        rutas = sorted(cache.glob("*.fits"))
        if not rutas:
            raise SystemExit("no hay nada en " + str(cache))
    else:
        ra, dec = tg.target_position(target_key, "2025-11-09")
        filas = tap_csv(
            "SELECT a.uri, p.energy_bandpassname, p.time_bounds_lower "
            "FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid "
            "WHERE 1 = CONTAINS(POINT('ICRS', " + repr(ra) + ", " + repr(dec) + "), p.poly) "
            "ORDER BY p.time_bounds_lower")
        espectro = elegir_espectro(filas)
        serie = elegir_serie(filas, det_serie, n_serie)
        pedidos = []
        for etiqueta, grupo in (("esp", espectro), ("ser", serie)):
            for k, fila in enumerate(grupo):
                det = (fila["energy_bandpassname"] or "").replace("SPHEREx-", "")
                pedidos.append((cache / (etiqueta + "_" + det + "_" + str(k) + ".fits"),
                                fila["uri"]))
        nuevos = [p for p in pedidos if not p[0].exists()]
        print("  " + str(len(pedidos)) + " recortes (" + str(len(nuevos))
              + " por bajar, ~" + str(len(nuevos) * 5) + " MB)", flush=True)
        for destino, uri in pedidos:
            bajar(uri, ra, dec, destino)
        rutas = sorted(cache.glob("*.fits"))

    frames = {"esp": [], "ser": []}
    for ruta in rutas:
        f = frame_de_fits(ruta, target_key)
        if f.detector in ("?", ""):
            f.detector = _det_de_nombre(ruta.name)
        frames[ruta.name[:3]].append(f)
    return frames["esp"], frames["ser"], det_serie


def validar_espectro(target_key, frames):
    """Cobertura espectral: cuantos detectores y que rango."""
    puntos = sp.extract(frames, target_key=target_key)
    if not puntos:
        return {"ok": False, "nota": "no se pudo medir ningun punto"}
    comb = sp.combine(puntos)
    dets = sorted({p.detector for p in puntos})
    snrs = [p.flux / p.flux_err for p in puntos if p.flux_err]
    return {
        "ok": len(dets) >= 5,
        "detectores": len(dets),
        "bandas": len(comb),
        "lambda_min": min(p.wavelength_um for p in puntos),
        "lambda_max": max(p.wavelength_um for p in puntos),
        "snr_mediana": float(np.median(snrs)) if snrs else float("nan"),
        "dudosos": sum(1 for p in puntos if p.quality != "ok"),
        "puntos": len(puntos),
    }


def validar_serie(target_key, frames, detector):
    """Serie temporal: cuantas fechas y si el brillo varia mas que su error."""
    if len(frames) < 3:
        return {"ok": False, "nota": "menos de 3 epocas"}
    puntos = sp.extract(frames, target_key=target_key)
    if len(puntos) < 3:
        return {"ok": False, "nota": "menos de 3 puntos medibles"}
    mjds, flujos, errs = sp.light_curve(puntos, detector=detector)
    bueno = np.isfinite(flujos) & np.isfinite(errs) & (errs > 0)
    if bueno.sum() < 3:
        return {"ok": False, "nota": "menos de 3 puntos con error valido"}
    f, e = flujos[bueno], errs[bueno]
    # Chi2 contra "brillo constante": si es >> 1, el objeto vario de verdad y no
    # es ruido. Ojo: dentro de un detector cada epoca puede caer en otro canal,
    # asi que parte de la dispersion es color, no variabilidad. Por eso esto es
    # una cota superior a la variabilidad, no una medicion de ella.
    peso = 1.0 / e ** 2
    media = float((f * peso).sum() / peso.sum())
    chi2 = float((((f - media) / e) ** 2).sum() / (bueno.sum() - 1))
    return {
        "ok": True,
        "epocas": int(bueno.sum()),
        "dias": float(mjds[bueno].max() - mjds[bueno].min()),
        "flujo_min": float(f.min()), "flujo_max": float(f.max()),
        "rango_relativo": float(f.max() / f.min()) if f.min() > 0 else float("inf"),
        "chi2_vs_constante": chi2,
        "varia": chi2 > 10.0,
    }


def validar_movimiento(target_key, frames):
    """Movimiento propio: cuanto se corre y si la resta lo muestra."""
    info = tg.get_target(target_key)
    if info["pm_correction"] != "required":
        return {"ok": True, "aplica": False,
                "nota": "movimiento propio despreciable: "
                        + str(info["astrometry"]["pm_total_arcsec_yr"]) + " arcsec/ano"}
    if len(frames) < 2:
        return {"ok": False, "aplica": True, "nota": "hacen falta 2 epocas"}

    orden = sorted(frames, key=lambda f: f.mjd)

    # Hay que elegir un par del MISMO CANAL, no simplemente los dos extremos.
    # Las exposiciones de un detector caen en canales distintos segun donde
    # apunto el barrido, asi que dos fechas lejanas casi nunca son comparables.
    # comparable_pairs() los ordena por separacion temporal decreciente.
    pares = sb.comparable_pairs(orden)
    if not pares:
        arc, px = tg.drift_between(target_key, orden[0].mjd, orden[-1].mjd)
        return {"ok": False, "aplica": True, "arcsec": arc, "px": px,
                "dias": abs(orden[-1].mjd - orden[0].mjd), "restable": False,
                "nota": "ninguna pareja de epocas cae en el mismo canal; "
                        "hay que bajar mas"}
    i, j = pares[0]
    a, b = orden[j], orden[i]
    arc, px = tg.drift_between(target_key, b.mjd, a.mjd)

    ref_ra, ref_dec = tg.target_position(target_key, (a.mjd + b.mjd) / 2)
    cubo = al.align_frames([b, a], ra=ref_ra, dec=ref_dec)
    res = {"ok": True, "aplica": True, "arcsec": arc, "px": px,
           "dias": abs(a.mjd - b.mjd), "epocas": len(cubo),
           "pares_comparables": len(pares), "restable": True,
           "banda": cubo.wavelengths_um[0]}
    if len(cubo) < 2:
        res["restable"] = False
        res["nota"] = "el objetivo no entra en los dos recortes"
        return res
    diff, var, usable = sb.subtract_aligned(cubo, 1, 0)
    dip = sb.dipole_snr(diff, var, center=cubo.center, box=4)
    res["dipolo_detectado"] = dip["detected"]
    res["pos_snr"] = dip["pos_snr"]
    res["neg_snr"] = dip["neg_snr"]
    res["separacion_px"] = dip["separation_px"]
    return res


def validar_vecino(target_key, frames):
    """Contaminacion por un companero cercano, para eps Ind B."""
    info = tg.get_target(target_key)
    sep = info.get("companion_separation")
    if not sep or not frames:
        return None
    f = frames[0]
    x_obj, y_obj = al.target_pixel(f, target_key=target_key)
    vecino = sep["from"]
    ra_v, dec_v = tg.target_position(vecino, f.mjd)
    x_v, y_v = f.wcs.world_to_pixel_values(ra_v, dec_v)
    d = float(np.hypot(x_obj - float(x_v), y_obj - float(y_v)))
    return {
        "vecino": vecino, "separacion_px": d,
        "separacion_arcsec": d * 6.2,
        "dentro_de_la_apertura": d <= sp.DEFAULT_APERTURE_PX,
        "dentro_del_anillo": sp.BG_IN * sp.DEFAULT_APERTURE_PX <= d
                             <= sp.BG_OUT * sp.DEFAULT_APERTURE_PX,
        "en_el_recorte": 0 <= x_v < f.shape[1] and 0 <= y_v < f.shape[0],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("targets", nargs="*", default=None)
    ap.add_argument("--cache-only", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    claves = args.targets or tg.target_keys()
    for key in claves:
        info = tg.get_target(key)
        print("\n" + "=" * 70)
        print(info["label"] + "  (" + key + ")")
        print("  lo que pide el enunciado: " + info.get("demo", "-"))
        print("=" * 70, flush=True)

        esp, ser, det = cargar(key, args.cache_only)

        r = validar_espectro(key, esp)
        print("\n  ESPECTRO")
        if not r["ok"] and "nota" in r:
            print("    FALLA: " + r["nota"])
        else:
            print("    %d puntos en %d detectores, %d bandas, %.2f a %.2f um"
                  % (r["puntos"], r["detectores"], r["bandas"],
                     r["lambda_min"], r["lambda_max"]))
            print("    SNR mediana %.1f, %d puntos dudosos"
                  % (r["snr_mediana"], r["dudosos"]))
            print("    -> " + ("OK: cubre el rango completo" if r["ok"]
                               else "PARCIAL: faltan detectores"))

        s = validar_serie(key, ser, det)
        print("\n  SERIE TEMPORAL (" + det + ")")
        if not s["ok"]:
            print("    FALLA: " + s["nota"])
        else:
            print("    %d epocas en %.0f dias" % (s["epocas"], s["dias"]))
            print("    flujo %.3e a %.3e Jy  (factor %.2f)"
                  % (s["flujo_min"], s["flujo_max"], s["rango_relativo"]))
            print("    chi2 contra brillo constante: %.1f" % s["chi2_vs_constante"])
            print("    -> " + ("VARIA de forma significativa" if s["varia"]
                               else "compatible con brillo constante"))

        m = validar_movimiento(key, ser)
        print("\n  MOVIMIENTO PROPIO")
        if not m["aplica"]:
            print("    " + m["nota"])
        elif not m.get("restable"):
            print("    deriva %.2f arcsec = %.2f px en %.0f dias"
                  % (m["arcsec"], m["px"], m["dias"]))
            print("    -> NO se puede restar: " + m.get("nota", "?"))
        else:
            print("    deriva %.2f arcsec = %.2f px en %.0f dias  (%d pares del mismo canal)"
                  % (m["arcsec"], m["px"], m["dias"], m["pares_comparables"]))
            print("    dipolo: pos %.1f, neg %.1f sigma, separados %.2f px"
                  % (m["pos_snr"], m["neg_snr"], m["separacion_px"]))
            print("    -> " + ("DETECTADO" if m["dipolo_detectado"]
                               else "no detectado"))

        v = validar_vecino(key, esp)
        if v:
            print("\n  COMPANERO CERCANO")
            print("    %s a %.1f px = %.0f arcsec" % (v["vecino"], v["separacion_px"],
                                                      v["separacion_arcsec"]))
            print("    en la apertura: %s | en el anillo de fondo: %s | en el recorte: %s"
                  % (v["dentro_de_la_apertura"], v["dentro_del_anillo"], v["en_el_recorte"]))
            print("    -> " + ("CONTAMINA la medicion" if v["dentro_de_la_apertura"]
                               else "no contamina la apertura"))


if __name__ == "__main__":
    main()
