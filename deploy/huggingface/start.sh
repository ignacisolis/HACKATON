#!/bin/sh
# Baja la caché precalculada (si hace falta) y arranca la API en el puerto que espera Hugging Face.
set -e
CACHE_DIR="${SPHEREX_CACHE_DIR:-/app/cache}"

if [ ! -f "$CACHE_DIR/targets.json" ]; then
  if [ -n "$CACHE_TAR" ] && [ -f "$CACHE_TAR" ]; then
    echo "caché: extrayendo $CACHE_TAR"
    tar -xf "$CACHE_TAR" -C "$CACHE_DIR"
  elif [ -n "$CACHE_DATASET" ]; then
    echo "caché: bajando $CACHE_FILE de $CACHE_DATASET"
    TAR=$(python -c "
import os
from huggingface_hub import hf_hub_download
print(hf_hub_download(repo_id=os.environ['CACHE_DATASET'], filename=os.environ['CACHE_FILE'],
                      repo_type='dataset', local_dir='/tmp'))")
    tar -xf "$TAR" -C "$CACHE_DIR" && rm -f "$TAR"
  else
    echo "caché: sin CACHE_DATASET; los objetivos se bajarán de IRSA a pedido (lento)"
  fi
fi

exec uvicorn app.main:app --app-dir /app/src/backend --host 0.0.0.0 --port "${PORT:-7860}"
