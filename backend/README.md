# backend/ · API del visor SPHEREx

Rol A (Camilo). Python + FastAPI. Plan y estado: [`PLAN.md`](PLAN.md).

## Correr en local

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/uvicorn app.main:app --app-dir backend --port 8000
```

Documentación interactiva: http://localhost:8000/docs

Tests (sin red, IRSA simulado):

```bash
cd backend && ../.venv/bin/python -m pytest -q
```

## Estructura

| Archivo | Qué hace |
|---|---|
| `app/settings.py` | Lee `config/release.yaml` (release, URLs, bandas, caché). |
| `app/irsa.py` | **Único** módulo que habla con IRSA: consulta TAP y descarga de cutouts. |
| `app/cache.py` | Caché compacta en disco (sin PSF, ~55–110 KB por exposición). |
| `app/frames.py` | Lista de cuadros + descarga progresiva en segundo plano (máx. 8 hilos). |
| `app/render.py` | Remuestreo north-up y PNG. **Provisional** hasta `core.align()`. |
| `app/main.py` | Endpoints HTTP. |
| `app/precompute.py` | `python -m app.precompute`: deja en caché los objetivos de la demo (#26). |
| `app/release_update.py` | `python -m app.release_update [--apply]`: suma releases nuevos de IRSA (#28). |

## Endpoints (borrador hasta acordar `contracts/api.md`)

`ra`/`dec` aceptan grados (`133.79513`, `-7.24515`) o sexagesimal (`08h55m10.831s`, `-7d14m42.53s`).
`size` es el lado del recorte en grados (por defecto 0.1, máximo 0.3).

### `GET /api/frames?ra=&dec=&size=&band=&detector=`

Devuelve al instante la lista de cuadros ordenada por fecha y encola la descarga de los que faltan.
El frontend vuelve a pedir la lista hasta que llega `complete: true` (los cuadros ya listos traen `ready: true`).

```json
{
  "query": {"ra": 133.79513, "dec": -7.24515, "size": 0.1, "band": null, "detector": 5},
  "release": {"collections": ["spherex_qr2", "…"], "label": "…"},
  "count": 48, "pending": 0, "queued": 0, "complete": true,
  "frames": [
    {"id": "2025W19_1B_0231_4D5", "date": "2025-05-06T…Z", "mjd": 60801.3, "detector": 5,
     "wavelength_um": 4.1393, "band": 78, "version": "l2b-v20-2025-241",
     "collection": "spherex_qr2", "ready": true,
     "image_url": "/api/frame/2025W19_1B_0231_4D5/image.png?ra=…&dec=…&size=0.1",
     "meta_url": "/api/frame/2025W19_1B_0231_4D5/meta?ra=…&dec=…&size=0.1"}
  ]
}
```

- `band` (1–102) es **aproximada**: 17 canales log-espaciados por detector (ver `config/release.yaml`).
  Con `band` se filtra por detector y, cuando el λ ya se conoce, por banda.
- `wavelength_um` es el λ del píxel del objetivo en esa exposición (`WCS-WAVE`).

### `GET /api/coverage?ra=&dec=&size=`

Qué hay en ese punto sin bajar ningún cutout: total, observaciones por detector y por colección,
fechas, **épocas** (visitas de ~6 meses) y, para lo ya cacheado, cuántas exposiciones caen en cada banda
(`bands`, con `bands_known` = cuántas tienen λ conocido). Sirve para el selector de banda.

### `GET /api/targets`

Objetivos de la demo con las coordenadas **exactas** que están precalculadas (`view_query`, `frames_url`).
El frontend debe usar esas coordenadas para que carguen al instante desde la caché.

### `GET /api/frame/{id}/image.png?ra=&dec=&size=&layer=&bits=&vmin=&vmax=`

PNG en escala de grises, norte arriba y este a la izquierda, centrado en `ra`/`dec`.
`layer`: `image` (por defecto), `image-zodi`, `variance` o `flags` (RGBA transparente con los bits de `bits=21,19`).

### `GET /api/frame/{id}/meta?ra=&dec=&size=`

Metadata del header (fecha, exposición, λ, banda, FWHM de la PSF, calidad L1/L2) y, por cada bit de FLAGS,
su nombre (tomado de `MP_*` del propio FITS), la fracción de píxeles marcados y si está prendido en el objetivo.

## Releases (C1)

Cada Quick Release de SPHEREx (`spherex_qr2`, `spherex_qr3`, …) trae **exposiciones nuevas**, no reprocesa
las anteriores; por eso `config/release.yaml` tiene una **lista** de colecciones que se suman
(incluye los campos *deep*; nunca las `*_cal`). Para incorporar un release nuevo:

```bash
cd backend
../.venv/bin/python -m app.release_update                        # ver qué hay en IRSA vs. config
../.venv/bin/python -m app.release_update --apply --precompute   # sumar, limpiar consultas, tests y precálculo
```

## Precálculo de la demo (#26)

```bash
cd backend && ../.venv/bin/python -m app.precompute   # lee config/targets.yaml (formato en app/precompute.py)
```

Sin `config/targets.yaml` usa WISE 0855 con las coordenadas del enunciado. Si el objetivo trae
`epoch` y movimiento propio, el recorte se centra en su posición de 2026 (no en la del catálogo).

## CI

`.github/workflows/backend-tests.yml` corre los tests en cada PR que toque `backend/` o `config/`.
