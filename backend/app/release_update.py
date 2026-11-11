"""Actualiza el backend a los releases de SPHEREx publicados en IRSA (#28, C1).

Uso (desde backend/):
    python -m app.release_update            # muestra qué hay en IRSA vs. config (no cambia nada)
    python -m app.release_update --apply    # suma las colecciones nuevas, limpia consultas y corre los tests
    python -m app.release_update --apply --precompute   # y además vuelve a precalcular la demo

Cada Quick Release (qr2, qr3, …) trae exposiciones NUEVAS, así que las colecciones se suman.
Las de calibración (*_cal) nunca se agregan. Los cutouts cacheados siguen sirviendo:
solo se borran las listas de observaciones por posición (cache/queries/).
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from astropy.time import Time

from . import irsa
from .settings import REPO_ROOT, config_path, get_settings, load_settings

_COLLECTIONS_LINE = re.compile(r"^(?P<indent>\s*)collections:\s*\[[^\]]*\]\s*$", re.MULTILINE)


def science_collections(available: list[dict]) -> list[str]:
    return [c["collection"] for c in available
            if c["collection"].startswith("spherex_") and not c["collection"].endswith("_cal")]


def write_collections(path: Path, collections: list[str]) -> None:
    """Reescribe solo la línea `collections: [...]` del YAML, conservando comentarios y orden."""
    text = path.read_text()
    if not _COLLECTIONS_LINE.search(text):
        raise SystemExit(f"no encontré una línea 'collections: [...]' en {path}")
    new = _COLLECTIONS_LINE.sub(lambda m: f"{m['indent']}collections: [{', '.join(collections)}]", text, count=1)
    path.write_text(new)
    load_settings(path)  # valida que el YAML siga siendo correcto


def run_tests() -> int:
    backend = REPO_ROOT / "backend"
    return subprocess.call([sys.executable, "-m", "pytest", "-q", "-p", "no:warnings"], cwd=backend)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="escribir los cambios en config/release.yaml")
    ap.add_argument("--precompute", action="store_true", help="tras aplicar, precalcular los objetivos")
    args = ap.parse_args(argv)

    s = get_settings()
    print("Consultando colecciones en IRSA (≈1 min)…")
    available = irsa.list_collections(s)
    configured = set(s.collections)
    for c in available:
        mark = "✓ en uso" if c["collection"] in configured else ("· calibración" if c["collection"].endswith("_cal") else "+ NUEVA")
        d0, d1 = (Time(c[k], format="mjd").isot[:10] if c[k] is not None else "sin fechas" for k in ("mjd_min", "mjd_max"))
        print(f"  {c['collection']:22s} {c['n']:>9,d} planos  {d0} → {d1}  {mark}")

    gone = configured - {c["collection"] for c in available}
    if gone:
        print(f"[aviso] en config pero ya no en IRSA: {', '.join(sorted(gone))}")
    wanted = [c for c in science_collections(available)]
    new = [c for c in wanted if c not in configured]
    if not new and not gone:
        print("Config al día: no hay colecciones nuevas.")
        return 0
    if not args.apply:
        print(f"Para usar {', '.join(new) or '(sin nuevas)'}: python -m app.release_update --apply")
        return 0

    final = [c for c in wanted if c in configured or c in new]
    write_collections(config_path(), final)
    print(f"config/release.yaml → collections: {final}")
    queries = s.cache_dir / "queries"
    if queries.exists():
        shutil.rmtree(queries)
        print("Caché de consultas borrada (los cutouts se conservan).")
    code = run_tests()
    if code:
        print("Los tests fallaron: revisa antes de desplegar.")
        return code
    if args.precompute:
        from . import precompute
        get_settings.cache_clear()
        return precompute.main([])
    return 0


if __name__ == "__main__":
    sys.exit(main())
