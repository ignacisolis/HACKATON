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

## Endpoints (borrador hasta acordar `contracts/api.md`)

`ra`/`dec` aceptan grados (`133.79513`, `-7.24515`) o sexagesimal (`08h55m10.831s`, `-7d14m42.53s`).
`size` es el lado del recorte en grados (por defecto 0.1, máximo 0.3).

### `GET /api/frames?ra=&dec=&size=&band=&detector=`

Devuelve al instante la lista de cuadros ordenada por fecha y encola la descarga de los que faltan.
El frontend vuelve a pedir la lista hasta que llega `complete: true` (los cuadros ya listos traen `ready: true`).

```json
{
  "query": {"ra": 133.79513, "dec": -7.24515, "size": 0.1, "band": null, "detector": 5},
  "release": {"name": "qr2", "label": "SPHEREx Quick Release 2"},
  "count": 48, "pending": 0, "queued": 0, "complete": true,
  "frames": [
    {"id": "2025W19_1B_0231_4D5", "date": "2025-05-06T…Z", "mjd": 60801.3, "detector": 5,
     "wavelength_um": 4.1393, "band": 78, "version": "l2b-v20-2025-241", "ready": true,
     "image_url": "/api/frame/2025W19_1B_0231_4D5/image.png?ra=…&dec=…&size=0.1",
     "meta_url": "/api/frame/2025W19_1B_0231_4D5/meta?ra=…&dec=…&size=0.1"}
  ]
}
```

- `band` (1–102) es **aproximada**: 17 canales log-espaciados por detector (ver `config/release.yaml`).
  Con `band` se filtra por detector y, cuando el λ ya se conoce, por banda.
- `wavelength_um` es el λ del píxel del objetivo en esa exposición (`WCS-WAVE`).

### `GET /api/frame/{id}/image.png?ra=&dec=&size=&layer=&bits=&vmin=&vmax=`

PNG en escala de grises, norte arriba y este a la izquierda, centrado en `ra`/`dec`.
`layer`: `image` (por defecto), `image-zodi`, `variance` o `flags` (RGBA transparente con los bits de `bits=21,19`).

### `GET /api/frame/{id}/meta?ra=&dec=&size=`

Metadata del header (fecha, exposición, λ, banda, FWHM de la PSF, calidad L1/L2) y, por cada bit de FLAGS,
su nombre (tomado de `MP_*` del propio FITS), la fracción de píxeles marcados y si está prendido en el objetivo.

## Cambiar de release (C1)

Editar `config/release.yaml` (`release.name`, `release.versions`) y borrar `cache/`. No hay que tocar código.
