# Desplegar el backend en Render, plan gratis (tarea 13)

Plan gratis de Render: 512 MB de RAM, 0.1 CPU, sin tarjeta. El contenedor se construye con
`deploy/render/Dockerfile` y al arrancar baja la caché precalculada (391 MB: cuadros, índice y
espectros de los 4 objetivos) del dataset público
[Camilocs7/spherex-cache](https://huggingface.co/datasets/Camilocs7/spherex-cache).

**Probado en local con los mismos límites** (`docker run --memory=512m --cpus=0.1`, 2026-11-11):
arranca en ~90 s, usa ~180 MB de RAM, y ya en caliente responde en 0.3–2.5 s
(`/frames`, `/png`, `/spectrum`, `/diff`, `/pairs`, `/coverage`).

> Hugging Face Spaces quedó descartado: desde 2026 los Spaces Docker en CPU gratis piden PRO
> (error 402 al crearlo). La carpeta `deploy/huggingface/` queda por si se paga PRO.

## Crear el servicio (una vez, en el panel de Render)

1. Entrar a https://dashboard.render.com (con Google, la cuenta de Camilo).
2. **New +** → **Web Service** → pestaña **Public Git Repository** →
   `https://github.com/ignacisolis/HACKATON` → **Connect**.
3. Completar:

   | Campo | Valor |
   |---|---|
   | Name | `spherex-api` |
   | Language / Runtime | **Docker** |
   | Branch | `main` |
   | Region | Oregon (o la más cercana) |
   | Root Directory | *(vacío)* |
   | Dockerfile Path | `./deploy/render/Dockerfile` |
   | Docker Build Context | `.` |
   | Instance Type | **Free** |

4. **Environment Variables** (*Add Environment Variable*):

   | Key | Value |
   |---|---|
   | `CACHE_DATASET` | `Camilocs7/spherex-cache` |
   | `SPHEREX_SPECTRUM_MAX_FRAMES` | `600` |

5. **Advanced** → **Health Check Path**: `/api/health`.
6. **Deploy Web Service**. El build tarda ~3–5 min y el primer arranque ~1.5 min más.

La URL queda como `https://spherex-api.onrender.com` (o con un sufijo si el nombre está tomado).

## Probar

```bash
curl https://spherex-api.onrender.com/api/health
curl "https://spherex-api.onrender.com/api/frames?target=wise_0855&detector=D6&prefetch=false"
```

Y pasarle a Bruno: `VITE_API_BASE=https://spherex-api.onrender.com`.

## Alternativa: Blueprint (`render.yaml`)

`render.yaml` en la raíz describe el mismo servicio. Para usarlo (**New + → Blueprint**) Render
necesita acceso al repo por la GitHub App, que en un repo de `ignacisolis` instala Ignacio. Con
Blueprint, cada merge a `main` despliega solo; con *Public Git Repository* hay que pulsar
**Manual Deploy → Deploy latest commit** (o usar el *Deploy Hook* de Settings).

## Redespliegue automático (Deploy Hook)

`.github/workflows/deploy-render.yml` redespliega cuando `main` cambia **y** los tests del
backend pasan. Configurarlo una vez:

1. **Camilo**, en Render: servicio `spherex-api` → **Settings → Deploy Hook** → copiar la URL.
   Es secreta (cualquiera con ella puede redesplegar): pasarla a Ignacio por privado, nunca en
   el repo, en un PR ni en Notion.
2. **Ignacio** (admin del repo): GitHub → *Settings → Secrets and variables → Actions → New
   repository secret* → nombre `RENDER_DEPLOY_HOOK`, valor la URL.

Sin el secreto el workflow no hace nada y hay que usar **Manual Deploy → Deploy latest commit**.

## Mantener despierto el día de la demo

`.github/workflows/keepalive-render.yml` pinguea `/api/health` cada 5 min del 14 al 16 de
noviembre (UTC). Corre solo desde `main`. Para probarlo: *Actions → keepalive-render → Run
workflow*. Igual conviene abrir `/api/health` antes de presentar: GitHub puede atrasar los cron.

## Mejores restas por objetivo

`python -m app.best_pairs` (desde `backend/`) prueba ~40 pares por detector, mide el dipolo y
lo contrasta con el movimiento propio esperado; `/api/targets` lo expone como `best_pair` y
`motion`. Resultado (2026-11-12): **eps Ind B confirmado en 6/6 detectores** (mejor D2, S/N 92.6,
521 días); WISE 0855 solo **indicio** (3/6, S/N 3–5: no presentarlo como detección); RW Aur y
R Dra sin movimiento, como corresponde. Va dentro de la caché (`best_pairs.json`).

## Cosas a saber del plan gratis

- **Se duerme tras 15 min sin visitas** y despertar tarda ~1.5 min (vuelve a bajar la caché).
  **Antes de la presentación, abrir `/api/health` un par de minutos antes.**
- El disco es efímero: lo que baje de IRSA para coordenadas fuera de la demo se pierde al dormir.
- Un espectro de más de 600 exposiciones que no venga precalculado responde **503 `too_heavy`**
  en vez de quedarse sin memoria. Los 4 objetivos vienen precalculados.
- Si cambia el release o se agregan objetivos: `python -m app.precompute` en local,
  `python deploy/huggingface/pack_cache.py cache/spherex-cache.tar`, subirlo al dataset
  (`hf upload Camilocs7/spherex-cache cache/spherex-cache.tar spherex-cache.tar --repo-type dataset`)
  y en Render **Manual Deploy → Restart service**.
