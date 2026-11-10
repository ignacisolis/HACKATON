"""Precalcula en caché los objetivos de la demo (#26), para que carguen sin tocar IRSA.

Uso (desde backend/):
    python -m app.precompute                 # todos los objetivos
    python -m app.precompute --only wise0855 # uno solo
    python -m app.precompute --list          # ver objetivos y centro calculado

Lee config/targets.yaml (lo mantiene Ciencia). Formato esperado:

    center_epoch: 2026.0          # año al que se llevan las coordenadas (mitad de los datos)
    targets:
      - name: WISE 0855
        slug: wise0855
        ra: "08h55m10.831s"       # grados o sexagesimal
        dec: "-07d14m42.53s"
        epoch: 2010.5             # año de esas coordenadas (opcional)
        pmra_masyr: -8100         # μα* = μα·cos δ, mas/año (opcional)
        pmdec_masyr: 700          # mas/año (opcional)
        size_deg: 0.1             # opcional
        source: "SIMBAD ..."      # de dónde salen los números

Si el archivo no existe, usa WISE 0855 con las coordenadas del enunciado y sin movimiento propio.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml
from astropy import units as u
from astropy.coordinates import SkyCoord

from . import cache, frames, irsa
from .settings import REPO_ROOT, Settings, get_settings

TARGETS_FILE = REPO_ROOT / "config" / "targets.yaml"
DEFAULT_CENTER_EPOCH = 2026.0
FALLBACK = {
    "targets": [{
        "name": "WISE 0855", "slug": "wise0855",
        "ra": "08h55m10.831s", "dec": "-07d14m42.53s",
        "source": "enunciado del hackathon (época y movimiento propio sin verificar)",
    }]
}


def load_targets(path: Path = TARGETS_FILE) -> tuple[list[dict], float]:
    cfg = yaml.safe_load(path.read_text()) if path.exists() else FALLBACK
    return cfg["targets"], float(cfg.get("center_epoch", DEFAULT_CENTER_EPOCH))


def center_of(t: dict, center_epoch: float, s: Settings) -> tuple[float, float, float]:
    """(ra, dec, size) del recorte, con las coordenadas llevadas a center_epoch si hay movimiento propio."""
    sexa = any(ch in str(t["ra"]) for ch in "hms: ")
    c = SkyCoord(str(t["ra"]), str(t["dec"]), unit=(u.hourangle if sexa else u.deg, u.deg))
    ra, dec = float(c.ra.deg), float(c.dec.deg)
    if t.get("epoch") is not None and (t.get("pmra_masyr") or t.get("pmdec_masyr")):
        dt = center_epoch - float(t["epoch"])
        dec_new = dec + float(t.get("pmdec_masyr") or 0) * dt / 3.6e6
        ra += float(t.get("pmra_masyr") or 0) * dt / 3.6e6 / math.cos(math.radians((dec + dec_new) / 2))
        dec = dec_new
    return round(ra % 360, 5), round(dec, 5), float(t.get("size_deg") or s.default_size_deg)


def precompute_target(t: dict, center_epoch: float, s: Settings, log=print) -> dict:
    ra, dec, size = center_of(t, center_epoch, s)
    t0 = time.time()
    obs = frames.observations_at(ra, dec, s)
    ok, failed = 0, []
    with ThreadPoolExecutor(max_workers=s.max_workers) as ex:
        futs = {ex.submit(cache.get_cutout, o, ra, dec, size, s): o for o in obs}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                f.result()
                ok += 1
            except irsa.IrsaError:
                failed.append(futs[f])
            if i % 25 == 0 or i == len(obs):
                log(f"  {t['slug']}: {i}/{len(obs)} ({ok} ok, {len(failed)} fallidos)")
    for o in list(failed):  # un reintento en serie: IRSA suele dar 503 transitorios
        try:
            cache.get_cutout(o, ra, dec, size, s)
            failed.remove(o)
            ok += 1
        except irsa.IrsaError:
            pass
    q = f"ra={ra}&dec={dec}&size={size:g}"
    return {
        "name": t["name"], "slug": t["slug"], "ra": ra, "dec": dec, "size": size,
        "source": t.get("source", ""), "frames": len(obs), "cached": ok,
        "failed": [o.id for o in failed], "seconds": round(time.time() - t0, 1),
        "frames_url": f"/api/frames?{q}", "view_query": q,
    }


def summary_path(s: Settings) -> Path:
    return s.cache_dir / "targets.json"


def load_summary(s: Settings | None = None) -> list[dict]:
    """Lo que devuelve /api/targets: lo precalculado, o la lista sin precalcular."""
    s = s or get_settings()
    p = summary_path(s)
    if p.exists():
        return json.loads(p.read_text())
    targets, epoch = load_targets()
    out = []
    for t in targets:
        ra, dec, size = center_of(t, epoch, s)
        q = f"ra={ra}&dec={dec}&size={size:g}"
        out.append({"name": t["name"], "slug": t["slug"], "ra": ra, "dec": dec, "size": size,
                    "source": t.get("source", ""), "frames": None, "cached": 0, "failed": [],
                    "frames_url": f"/api/frames?{q}", "view_query": q})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", help="slugs a precalcular")
    ap.add_argument("--list", action="store_true", help="solo muestra objetivos y centros")
    args = ap.parse_args(argv)
    s = get_settings()
    targets, epoch = load_targets()
    if not TARGETS_FILE.exists():
        print(f"[aviso] no existe {TARGETS_FILE}: uso WISE 0855 del enunciado")
    if args.only:
        targets = [t for t in targets if t["slug"] in args.only]
    if args.list:
        for t in targets:
            print(t["slug"], *center_of(t, epoch, s), t.get("source", ""))
        return 0

    previous = {r["slug"]: r for r in (json.loads(summary_path(s).read_text()) if summary_path(s).exists() else [])}
    for t in targets:
        print(f"→ {t['name']}")
        previous[t["slug"]] = precompute_target(t, epoch, s)
        r = previous[t["slug"]]
        print(f"  listo: {r['cached']}/{r['frames']} cuadros en {r['seconds']} s; fallidos: {len(r['failed'])}")
    summary_path(s).parent.mkdir(parents=True, exist_ok=True)
    summary_path(s).write_text(json.dumps(list(previous.values()), indent=2, ensure_ascii=False))
    return 1 if any(r["failed"] for r in previous.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
