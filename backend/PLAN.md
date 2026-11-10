# Plan de trabajo · rama `back` (Rol A · Datos y backend)

Responsable: Camilo. Carpeta: `backend/` (+ `config/release.yaml`).
Stack: Python 3.12 + FastAPI. Los IDs (#) son los del Tablero SPHEREx en Notion.

## Principios

- **Un solo módulo habla con IRSA** (`app/irsa.py`). Si IRSA cambia, se toca un archivo.
- **Nada de release en el código.** Release, URLs y bandas viven en `config/release.yaml` (C1).
- **Caché compacta**: de cada cutout (~5 MB, 99 % PSF) se guarda solo IMAGE, VARIANCE,
  FLAGS, ZODI, WCS y mapa de λ (~100 KB). Una consulta repetida no toca IRSA.
- **La ciencia es de `core/`** (Nacho). El backend llama a funciones puras (`core.align`,
  `core.subtract`, `core.spectrum`). Mientras no existan, hay un reemplazo mínimo marcado
  como provisional.

## Fases

| Fase | # | Tarea | Listo cuando | Estado |
|---|---|---|---|---|
| 1 | 12 | `config/release.yaml` + `app/settings.py` | Cambiar de release = editar el YAML | En curso |
| 1 | 9 | `app/irsa.py` (TAP + cutouts) | Lista las observaciones de WISE 0855 | En curso |
| 1 | 10 | `app/cache.py` caché compacta sin PSF | ~100 KB/exposición; 2ª consulta no toca IRSA | En curso |
| 1 | 11 | `GET /api/frames` | Valida contra `contracts/fixtures/frames.json` | En curso (contrato pendiente) |
| 1 | 13 | Desplegar backend público | URL pública responde `/api/frames` para WISE 0855 | Por hacer |
| 2 | 20 | `GET /api/frame/{id}/meta` con bits de FLAGS | Valida contra `contracts/fixtures/frame-meta.json` | En curso (bits leídos del header) |
| 3 | 24 | `GET /api/spectrum` | Llama a `core.spectrum()` y valida contra fixture | Bloqueado por `core.spectrum()` |
| 4 | 26 | Precalcular los 4 objetivos | Cargan desde caché sin tocar IRSA | Bloqueado por `config/targets.yaml` |
| 5 | 28 | Script de release + tests | Un release nuevo entra con un comando y los tests pasan | Por hacer |

## Hallazgos de esta rama (útiles para el equipo)

- El **header de FLAGS trae el significado de cada bit** (`MP_*`): 0 TRANSIENT, 1 OVERFLOW,
  2 SUR_ERROR, 4 PHANTOM, 5 REFERENCE, 6 NONFUNC, 7 DICHROIC, 9 MISSING_DATA, 10 HOT,
  11 COLD, 12 FULLSAMPLE, 14 PHANMISS, 15 NONLINEAR, 17 PERSIST, 19 OUTLIER, **21 SOURCE**
  (el bit que domina en la Fase 0 es "píxel de una fuente conocida", no contaminación).
  El backend los lee del archivo; `config/flags.yaml` (Nacho) puede sumar descripciones largas.
- Para WISE 0855, todas las observaciones son del release `qr2`, con 13 versiones de
  procesamiento (`l2b-v20-2025-241` … `l2b-v24-2026-135`) y **sin exposiciones duplicadas**
  entre versiones.
- Rangos por detector (TAP, µm): D1 0.746–1.117 · D2 1.103–1.650 · D3 1.630–2.435 ·
  D4 2.403–3.847 · D5 3.811–4.430 · D6 4.412–5.010. **Los rangos se solapan levemente.**
- TAP: ~3–10 s. Un cutout de 0.1°: ~14 s y 5.1 MB. Por eso la API responde la lista al
  instante y los cuadros se bajan en segundo plano (carga progresiva).

## API que implementa hoy la rama (borrador hasta acordar `contracts/api.md`)

- `GET /api/health`
- `GET /api/frames?ra=&dec=&size=&band=&detector=` → lista de cuadros ordenados por fecha.
  `ra`/`dec` en grados o sexagesimal (`08h55m10.831s`). `band` = 1–102 (aprox.), `detector` = 1–6.
- `GET /api/frame/{id}/image.png?ra=&dec=&size=&layer=` → cuadro renderizado (north-up).
- `GET /api/frame/{id}/meta?ra=&dec=&size=` → metadata del header + bits de FLAGS en el recorte.

## Pendiente con el equipo

- Que Bruno suba el kit (`contracts/api.md`, fixtures, `docs/EQUIPO.md`) para ajustar las respuestas.
- `config/targets.yaml` (Nacho) para precalcular los 4 objetivos.
- Proteger `main` no es posible en repo privado con plan gratuito: acuerdo de "todo entra por PR".
