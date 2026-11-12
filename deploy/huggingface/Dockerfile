# Backend del visor SPHEREx para un Space de Hugging Face (SDK: docker).
#
# El Space solo necesita este Dockerfile, start.sh y README.md: el código se clona del repo
# público de GitHub al construir, y la caché precalculada (~390 MB) se baja de un dataset de
# Hugging Face al arrancar (variable CACHE_DATASET). Ver deploy/huggingface/DEPLOY.md.
FROM python:3.12-slim

ARG REPO=https://github.com/ignacisolis/HACKATON.git
ARG REF=main

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face corre los contenedores con el usuario 1000.
RUN useradd -m -u 1000 user
WORKDIR /app

# Rompe la caché de Docker cuando cambia la rama: cada rebuild trae el último commit.
ADD https://api.github.com/repos/ignacisolis/HACKATON/commits/${REF} /tmp/commit.json
RUN git clone --depth 1 --branch ${REF} ${REPO} /app/src \
    && pip install --no-cache-dir -r /app/src/requirements.txt -r /app/src/backend/requirements.txt \
       huggingface_hub

COPY --chown=user start.sh /app/start.sh
RUN chmod +x /app/start.sh && mkdir -p /app/cache && chown -R user /app

USER user
ENV SPHEREX_CACHE_DIR=/app/cache \
    CACHE_FILE=spherex-cache.tar \
    PORT=7860 \
    PYTHONUNBUFFERED=1
EXPOSE 7860
CMD ["/app/start.sh"]
