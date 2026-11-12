# Desplegar el backend en Hugging Face Spaces (tarea 13)

> **Descartado (2026-11-11):** Hugging Face ahora pide PRO para Spaces Docker en CPU gratis (error 402). Se usa Render: ver `deploy/render/DEPLOY.md`. El dataset `Camilocs7/spherex-cache` sí se usa.

Gratis (CPU basic: 2 vCPU, 16 GB de RAM). El Space solo lleva `Dockerfile`, `start.sh` y
`README.md`: al construir clona `ignacisolis/HACKATON` (público) y al arrancar baja la caché
precalculada de un **dataset** de Hugging Face. URL final: `https://<usuario>-spherex-api.hf.space`.

Probado en local con Docker (2026-11-11): la imagen construye en ~70 s, arranca con los 4 objetivos
en memoria en < 1 s gracias al índice, y `/api/frames`, `/png`, `/diff` (con headers CORS),
`/pairs`, `/coverage` y `/api/spectrum` responden.

## Antes de empezar

- El Dockerfile clona la rama `main`. **Fusionar primero el PR #7** (bandas de `core.bands`,
  `/api/diff`, `display_range`, índice). Para probar sin esperar, cambiar `ARG REF=main` por
  `ARG REF=back` en el Dockerfile que se sube al Space.
- Caché precalculada en `cache/` (`python -m app.precompute` desde `backend/`).

## Pasos (los hace Camilo: cuenta y token son personales)

Desde la raíz del repo. `<usuario>` es tu usuario de Hugging Face.

1. **Crear la cuenta** en https://huggingface.co/join y un **token con permiso de escritura** en
   https://huggingface.co/settings/tokens.

2. **Iniciar sesión en la CLI** (pega el token cuando lo pida; no lo guardes en el repo):

   ```bash
   .venv/bin/pip install huggingface_hub
   .venv/bin/hf auth login
   ```

3. **Empaquetar y subir la caché** como dataset público (son datos públicos de la NASA, ~390 MB):

   ```bash
   .venv/bin/python deploy/huggingface/pack_cache.py
   .venv/bin/hf repos create <usuario>/spherex-cache --repo-type dataset --exist-ok
   .venv/bin/hf upload <usuario>/spherex-cache spherex-cache.tar --repo-type dataset
   ```

4. **Crear el Space y subir sus 3 archivos:**

   ```bash
   .venv/bin/hf repos create <usuario>/spherex-api --type space --sdk docker --exist-ok
   .venv/bin/hf upload <usuario>/spherex-api deploy/huggingface . --repo-type space --exclude "*.py" --exclude "DEPLOY.md"
   ```

5. **Decirle al Space dónde está la caché:**

   ```bash
   .venv/bin/hf spaces variables add <usuario>/spherex-api -e CACHE_DATASET=<usuario>/spherex-cache
   ```

6. **Esperar el build** (~3 min) y probar:

   ```bash
   .venv/bin/hf spaces logs <usuario>/spherex-api --build   # log del build; sin --build, el de la app
   curl https://<usuario>-spherex-api.hf.space/api/health
   curl "https://<usuario>-spherex-api.hf.space/api/frames?target=wise_0855&detector=D6"
   ```

7. **Pasarle la URL a Bruno** para el frontend: es `VITE_API_BASE=https://<usuario>-spherex-api.hf.space` (ver `frontend/src/api/client.ts`). El backend ya permite CORS desde cualquier origen.

## Mantenimiento

- **Código nuevo en `main`:** `.venv/bin/hf spaces restart <usuario>/spherex-api --factory-reboot`
  (o *Settings → Factory rebuild*). El Dockerfile vuelve a clonar el último commit.
- **Release nuevo de SPHEREx:** `python -m app.release_update --apply --precompute` en local,
  repetir el paso 3 (el mismo archivo se reemplaza) y reiniciar el Space.
- El Space gratis **se duerme tras 48 h sin visitas** y tarda ~1 min en despertar (baja la caché de
  nuevo). Antes de la presentación, abrir `/api/health` para despertarlo.
- Coordenadas fuera de la demo: el backend baja los cutouts de IRSA a pedido (carga progresiva). Ese
  disco es efímero: se pierde al reiniciar, la demo no.
