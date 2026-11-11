# Plan de trabajo · rama `back` (Rol A · Datos y backend)

Responsable: Camilo. Carpeta: `backend/` (+ `config/release.yaml`).
Stack: Python 3.12 + FastAPI. Los IDs (#) son los del Tablero SPHEREx en Notion.
**Entrega: 15 de noviembre de 2026.**

## Principios

- **Un solo módulo habla con IRSA** (`app/irsa.py`). Si IRSA cambia, se toca un archivo.
- **Nada de release en el código.** Release, URLs y bandas viven en `config/release.yaml` (C1).
- **Caché compacta**: de cada cutout (~5 MB, 99 % PSF) se guarda solo IMAGE, VARIANCE,
  FLAGS, ZODI, WCS y mapa de λ (~100 KB). Una consulta repetida no toca IRSA.
- **La ciencia es de `core/`** (Nacho). El backend la llama solo desde `app/science.py`:
  `core.targets`, `core.flags`, `core.extract_spectrum`, `core.combine`, `core.light_curve`
  (los nombres reales; `core.align`/`core.subtract`/`core.spectrum` son los módulos).

## Fases

| Fase | # | Tarea | Listo cuando | Estado |
|---|---|---|---|---|
| 1 | 12 | `config/release.yaml` + `app/settings.py` | Cambiar de release = editar el YAML | En revisión (PR #1) |
| 1 | 9 | `app/irsa.py` (TAP + cutouts) | Lista las observaciones de WISE 0855 | En revisión (PR #1) |
| 1 | 10 | `app/cache.py` caché compacta sin PSF | ~100 KB/exposición; 2ª consulta no toca IRSA | En revisión (PR #1) |
| 1 | 11 | `GET /api/frames` | Valida contra `contracts/fixtures/frames.json` | Hecho (test_contract.py) |
| 1 | 13 | Desplegar backend público | URL pública responde `/api/frames` para WISE 0855 | Por hacer |
| 2 | 20 | `GET /api/frame/{id}/meta` con bits de FLAGS | Valida contra `contracts/fixtures/frame-meta.json` | Hecho (test_contract.py, usa `core.flags`) |
| 3 | 24 | `GET /api/spectrum` y `/api/lightcurve` | Llama a `core.extract_spectrum()` y valida contra fixture | Endpoint listo y validado con un core falso; responde 501 hasta la tarea 23 |
| 2 | — | `GET /api/coverage` (bandas, detectores, épocas) | El selector de banda sabe qué hay | Hecho |
| 4 | 26 | `app/precompute.py` + `GET /api/targets` | Los objetivos cargan desde caché sin tocar IRSA | Usa `config/targets.yaml` (Nacho); precálculo de los 4 en curso |
| 5 | 28 | `app/release_update.py` + CI | Un release nuevo entra con un comando y los tests pasan | Hecho |

## Hallazgos de esta rama (útiles para el equipo)

- El **header de FLAGS trae el significado de cada bit** (`MP_*`): 0 TRANSIENT, 1 OVERFLOW,
  2 SUR_ERROR, 4 PHANTOM, 5 REFERENCE, 6 NONFUNC, 7 DICHROIC, 9 MISSING_DATA, 10 HOT,
  11 COLD, 12 FULLSAMPLE, 14 PHANMISS, 15 NONLINEAR, 17 PERSIST, 19 OUTLIER, **21 SOURCE**
  (el bit que domina en la Fase 0 es "píxel de una fuente conocida", no contaminación).
  El backend los lee del archivo; `config/flags.yaml` (Nacho) puede sumar descripciones largas.
- **Hay más de un release en IRSA** (`spherex.obscore`): `spherex_qr2` (2025-05 → 2026-07),
  `spherex_qr3` (2026-07 → 2026-10), sus campos `*_deep` y `*_cal`. Cada QR trae exposiciones
  nuevas: se suman todas las de ciencia. Para WISE 0855 `qr3` no aporta (no se observó en ese tramo).
- Para WISE 0855, todas las observaciones son del release `qr2`, con 13 versiones de
  procesamiento (`l2b-v20-2025-241` … `l2b-v24-2026-135`) y **sin exposiciones duplicadas**
  entre versiones.
- Rangos por detector (TAP, µm): D1 0.746–1.117 · D2 1.103–1.650 · D3 1.630–2.435 ·
  D4 2.403–3.847 · D5 3.811–4.430 · D6 4.412–5.010. Según `docs/ciencia.md` 3.4 los detectores
  se encadenan sin solaparse (costuras de ~0.02 µm).
- TAP: ~3–10 s. Un cutout de 0.1°: ~14 s y 5.1 MB. Por eso la API responde la lista al
  instante y los cuadros se bajan en segundo plano (carga progresiva).

## API que implementa hoy la rama (sigue `contracts/api.md` v0; detalle en README.md)

- `GET /api/health`
- `GET /api/coverage?ra=&dec=&size=` → observaciones por detector, fecha, época y banda (sin bajar cutouts).
- `GET /api/targets` → objetivos de la demo con las coordenadas precalculadas.
- `GET /api/frames?ra=&dec=&size=&band=&detector=` → lista de cuadros ordenados por fecha.
  `ra`/`dec` en grados o sexagesimal (`08h55m10.831s`). `band` = 1–102 (aprox.), `detector` = 1–6.
- `GET /api/frame/{id}/png?…&stretch=&layer=&bits=` → cuadro renderizado (norte arriba).
- `GET /api/spectrum`, `GET /api/lightcurve` → `core/` (501 hasta la tarea 23).
- Todos aceptan `target=` (eps_ind_b, wise_0855, rw_aur, r_dra) en vez de `ra`/`dec`.
- `GET /api/frame/{id}/meta?ra=&dec=&size=` → metadata del header + bits de FLAGS en el recorte.

## Pendiente con el equipo

- Que Bruno y Nacho den el OK al contrato (decisiones del backend en `contracts/api.md`) para marcarlo v1.
- Tarea 23 (Nacho): `core.extract_spectrum`, `core.combine`, `core.light_curve`. El backend ya las llama.
- Proteger `main` no es posible en repo privado con plan gratuito: acuerdo de "todo entra por PR".
