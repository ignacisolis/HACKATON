# Backend del visor SPHEREx para Render (plan gratis: 512 MB de RAM, 0.1 CPU).
#
# Render construye desde la raíz del repo (dockerContext: .), así que se copia el código del
# commit que se despliega. La caché precalculada (~390 MB, con los espectros de los 4 objetivos)
# se baja al arrancar del dataset público de Hugging Face (CACHE_DATASET). Ver deploy/render/DEPLOY.md.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt /app/src/requirements.txt
COPY backend/requirements.txt /app/src/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/src/requirements.txt -r /app/src/backend/requirements.txt huggingface_hub

COPY core /app/src/core
COPY config /app/src/config
COPY contracts /app/src/contracts
COPY backend /app/src/backend
COPY deploy/huggingface/start.sh /app/start.sh
RUN chmod +x /app/start.sh && mkdir -p /app/cache

ENV SPHEREX_CACHE_DIR=/app/cache \
    CACHE_FILE=spherex-cache.tar \
    PORT=10000 \
    PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["/app/start.sh"]
