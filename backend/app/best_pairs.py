"""Busca, para cada objetivo, la resta de dos cuadros que mejor muestra su movimiento (O4).

Uso (desde backend/, con la caché precalculada):
    python -m app.best_pairs                   # los 4 objetivos
    python -m app.best_pairs --only wise_0855  # uno
    python -m app.best_pairs --per-detector 60 # cuántos pares probar por detector

Para cada detector toma los pares restables de mayor separación en el tiempo (/api/pairs),
mide el dipolo de cada resta con core.dipole_snr (ZODI restado, como /api/diff) y guarda el
mejor en cache/best_pairs.json, que /api/targets expone como `best_pair`. Así la web abre la
resta más convincente sin buscarla. Se mide en local porque son cientos de restas: en el
plan gratis de Render tardaría demasiado.

Criterio: primero los pares cuyo dipolo coincide con el movimiento propio esperado
(`motion_consistent`: dirección ≤ 45° y tamaño, ver frames.motion_check); después los
`detected` (dos lóbulos juntos, core.dipole_snr), y entre iguales el de mayor
min(pos_snr, neg_snr). Probar cientos de restas da falsos positivos: un `detected` sin
`motion_consistent` NO es movimiento del objetivo, y el pitch no debe presentarlo así.
`motion.claim` resume: "confirmado" si coincide en >= 4 de los 6 detectores, "indicio" con
1 a 3, "no" con ninguno.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from . import frames, irsa, precompute, science
from .settings import Settings, get_settings


# Probar cientos de restas da falsos positivos (y los residuos de PSF llegan a ~6σ). Que el
# dipolo coincida con el movimiento esperado en VARIOS detectores independientes es la prueba
# que vale: eps Ind B lo hace en los 6. Con 1 a 3 detectores se reporta solo como "indicio".
CONFIRM_MIN_DETECTORS = 4


def _score(info: dict) -> tuple:
    """Primero el movimiento confirmado (dipolo + dirección y tamaño esperados), después S/N."""
    d = info["dipole"]
    snr = min(d.get("pos_snr") or 0.0, d.get("neg_snr") or 0.0)
    mc = info.get("motion_check") or {}
    return (bool(mc.get("consistent")), bool(d.get("detected")), snr)


def _row(info: dict, q: frames.Query) -> dict:
    d = info["dipole"]
    a, b = info["a"]["id"], info["b"]["id"]
    return {
        "a": a, "b": b, "detector": info["a"]["detector"], "dt_days": round(info["dt_days"], 2),
        "wavelength_um": [info["a"]["wavelength_um"], info["b"]["wavelength_um"]],
        "detected": bool(d.get("detected")),
        "pos_snr": round(d.get("pos_snr") or 0.0, 2), "neg_snr": round(d.get("neg_snr") or 0.0, 2),
        "separation_px": d.get("separation_px"),
        "motion_consistent": bool((info.get("motion_check") or {}).get("consistent")),
        "motion_check": info.get("motion_check"),
        "diff_url": f"/api/diff?a={a}&b={b}&{q.qs}",
    }


def best_for_target(key: str, per_detector: int, s: Settings, log=print) -> dict:
    q = frames.resolve(None, None, s.default_size_deg, key)
    by_det: dict[str, dict] = {}
    tested = 0
    t0 = time.time()
    for det in range(1, 7):
        candidates = frames.pairs(q, detector=det, limit=per_detector, s=s)["pairs"]
        best = None
        for p in candidates:
            oa, ob = (frames.cache.load_observation(i, s) for i in (p["a"], p["b"]))
            try:
                info = frames.diff(q, oa, ob, True, s)["info"]
            except (frames.NotComparable, irsa.IrsaError):
                continue
            tested += 1
            if best is None or _score(info) > _score(best):
                best = info
        if best is not None:
            by_det[f"D{det}"] = _row(best, q)
            r = by_det[f"D{det}"]
            mc = r["motion_check"] or {}
            log(f"  {key} D{det}: {len(candidates)} pares, mejor S/N {min(r['pos_snr'], r['neg_snr']):.1f}"
                f" ({'detectado' if r['detected'] else 'no detectado'}, {r['dt_days']:.0f} días;"
                f" esperado {mc.get('expected_len_px')} px, medido {mc.get('measured_px')},"
                f" ángulo {mc.get('angle_deg')}° -> {'MOVIMIENTO' if r['motion_consistent'] else 'no confirma'})",
                flush=True)
    overall = max(by_det.values(),
                  key=lambda r: (r["motion_consistent"], r["detected"], min(r["pos_snr"], r["neg_snr"])),
                  default=None)
    n_ok = sum(1 for r in by_det.values() if r["motion_consistent"])
    claim = "confirmado" if n_ok >= CONFIRM_MIN_DETECTORS else ("indicio" if n_ok else "no")
    if overall is not None:
        overall = {**overall, "claim": claim}
    return {"key": key, "best": overall, "by_detector": by_det, "n_tested": tested,
            "motion": {"claim": claim, "detectors_consistent": n_ok, "detectors_tested": len(by_det)},
            "seconds": round(time.time() - t0, 1)}


def load(s: Settings | None = None) -> dict[str, dict]:
    s = s or get_settings()
    p = s.cache_dir / "best_pairs.json"
    return json.loads(p.read_text()) if p.exists() else {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", help="claves de targets.yaml")
    ap.add_argument("--per-detector", type=int, default=40, help="pares a probar por detector")
    args = ap.parse_args(argv)
    s = get_settings()
    done = {t["key"] for t in precompute.load_summary(s) if t.get("cached")}
    keys = [k for k in science.target_keys() if k in done and (not args.only or k in args.only)]
    out = load(s)
    for k in keys:
        print(f"→ {science.target_label(k)} ({k})", flush=True)
        out[k] = best_for_target(k, args.per_detector, s)
        b = out[k]["best"]
        if b:
            m = out[k]["motion"]
            print(f"  mejor: {b['detector']} S/N {min(b['pos_snr'], b['neg_snr']):.1f} · movimiento: "
                  f"{m['claim'].upper()} ({m['detectors_consistent']}/{m['detectors_tested']} detectores)"
                  f" · {out[k]['n_tested']} restas "
                  f"en {out[k]['seconds']} s", flush=True)
        (s.cache_dir / "best_pairs.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
