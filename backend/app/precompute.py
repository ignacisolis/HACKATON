"""Precalcula en caché los objetivos de la demo (#26), para que carguen sin tocar IRSA.

Uso (desde backend/):
    python -m app.precompute                   # los 4 objetivos de config/targets.yaml
    python -m app.precompute --only wise_0855  # uno o varios
    python -m app.precompute --list            # ver objetivos y centro del recorte

Los objetivos y su astrometría vienen de config/targets.yaml (rol C, generado desde
SIMBAD por core/fetch_targets.py). El recorte se centra donde está cada objetivo a
mitad de la ventana de SPHEREx, con el movimiento propio de core.targets: con las
coordenadas del enunciado WISE 0855 quedaría ~21 px fuera de lugar.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import cache, frames, irsa, science
from .settings import Settings, get_settings


def precompute_target(key: str, s: Settings, log=print) -> dict:
    q = frames.resolve(None, None, s.default_size_deg, key)
    t0 = time.time()
    obs = frames.observations_at(q.ra, q.dec, s)
    ok, failed = 0, []
    with ThreadPoolExecutor(max_workers=s.max_workers) as ex:
        futs = {ex.submit(cache.get_cutout, o, q.ra, q.dec, q.size, s): o for o in obs}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                f.result()
                ok += 1
            except irsa.IrsaError:
                failed.append(futs[f])
            if i % 50 == 0 or i == len(obs):
                log(f"  {key}: {i}/{len(obs)} ({ok} ok, {len(failed)} fallidos)", flush=True)
    for o in list(failed):  # un reintento en serie: IRSA suele dar 503 transitorios
        try:
            cache.get_cutout(o, q.ra, q.dec, q.size, s)
            failed.remove(o)
            ok += 1
        except irsa.IrsaError:
            pass
    try:  # el espectro queda en cache/spectra/ y viaja con la caché al servidor
        sp = frames.spectrum(q, s)
        log(f"  {key}: espectro de {sp['n_points']} bandas con {sp['n_epochs_used']} exposiciones", flush=True)
    except Exception as e:  # noqa: BLE001 - un espectro fallido no invalida los cuadros
        log(f"  {key}: no se pudo calcular el espectro: {e}", flush=True)
    return {**_entry(key, q), "frames": len(obs), "cached": ok,
            "failed": [o.id for o in failed], "seconds": round(time.time() - t0, 1)}


def _entry(key: str, q: frames.Query) -> dict:
    return {"key": key, "name": science.target_label(key), "ra": q.ra, "dec": q.dec, "size": q.size,
            "coord_epoch_applied": science.window_center(key)[2],
            "frames_url": f"/api/frames?target={key}", "view_query": f"target={key}"}


def summary_path(s: Settings) -> Path:
    return s.cache_dir / "targets.json"


def _read_summary(s: Settings) -> dict[str, dict]:
    p = summary_path(s)
    rows = json.loads(p.read_text()) if p.exists() else []
    return {r["key"]: r for r in rows if "key" in r}  # ignora entradas de formatos viejos


def load_summary(s: Settings | None = None) -> list[dict]:
    """Lo que devuelve /api/targets: los objetivos de targets.yaml y cuánto está en caché."""
    s = s or get_settings()
    from . import best_pairs  # import local: best_pairs importa este módulo

    done = _read_summary(s)
    best = best_pairs.load(s)
    out = []
    for key in science.target_keys():
        q = frames.resolve(None, None, s.default_size_deg, key)
        r = done.get(key)
        row = (r if r and (r["ra"], r["dec"]) == (q.ra, q.dec)
               else {**_entry(key, q), "frames": None, "cached": 0, "failed": []})
        # La resta que mejor muestra el movimiento (python -m app.best_pairs), o None.
        bp = best.get(key) or {}
        out.append({**row, "best_pair": bp.get("best"), "motion": bp.get("motion")})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", help="claves de targets.yaml a precalcular")
    ap.add_argument("--list", action="store_true", help="solo muestra objetivos y centros")
    args = ap.parse_args(argv)
    s = get_settings()
    keys = science.target_keys()
    if args.only:
        unknown = set(args.only) - set(keys)
        if unknown:
            print(f"objetivos desconocidos: {sorted(unknown)}. Opciones: {keys}")
            return 2
        keys = [k for k in keys if k in args.only]
    if args.list:
        for k in keys:
            ra, dec, epoch = science.window_center(k)
            print(f"{k:10s} {ra:10.5f} {dec:+9.5f}  (posición al {epoch})  {science.target_label(k)}")
        return 0

    p = summary_path(s)
    previous = _read_summary(s)
    for k in keys:
        print(f"→ {science.target_label(k)} ({k})", flush=True)
        previous[k] = r = precompute_target(k, s)
        print(f"  listo: {r['cached']}/{r['frames']} cuadros en {r['seconds']} s; fallidos: {len(r['failed'])}",
              flush=True)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(list(previous.values()), indent=2, ensure_ascii=False))
    return 1 if any(r["failed"] for r in previous.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
