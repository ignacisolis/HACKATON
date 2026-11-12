"""Empaqueta la caché de los objetivos precalculados en un solo .tar para subirlo a Hugging Face.

Uso (desde la raíz del repo, con la caché ya precalculada):
    .venv/bin/python deploy/huggingface/pack_cache.py            # -> spherex-cache.tar

Incluye solo lo que usa la demo: los cutouts de cada objetivo en su centro actual, sus fichas
de observación, las consultas, el índice de resúmenes y targets.json. Los .npz ya vienen
comprimidos, así que el .tar va sin comprimir.
"""
from __future__ import annotations

import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app import cache, frames, precompute  # noqa: E402
from app.settings import get_settings  # noqa: E402


def main(out: str = "spherex-cache.tar") -> int:
    s = get_settings()
    base = s.cache_dir
    files: set[Path] = {base / "targets.json"}
    for t in precompute.load_summary(s):
        if not t.get("cached"):
            print(f"[aviso] {t['key']} no está precalculado: python -m app.precompute --only {t['key']}")
            continue
        q = frames.resolve(None, None, t["size"], t["key"])
        files.add(base / "queries" / f"{q.ra:.5f}_{q.dec:+.5f}.json")
        idx = base / "index" / f"{frames._qkey(q)}.json"
        if idx.exists():
            files.add(idx)
        for o in frames.observations_at(q.ra, q.dec, s):
            files.add(base / "obs" / f"{o.id}.json")
            p = cache.get_cached_path(o.id, q.ra, q.dec, q.size, s)
            if p.exists():
                files.add(p)
    missing = [f for f in files if not f.exists()]
    if missing:
        print(f"[aviso] faltan {len(missing)} archivos, p. ej. {missing[0]}")
    files = sorted(f for f in files if f.exists())
    with tarfile.open(out, "w") as tar:
        for f in files:
            tar.add(f, arcname=str(f.relative_to(base)))
    size = Path(out).stat().st_size / 1e6
    print(f"{out}: {len(files)} archivos, {size:.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
