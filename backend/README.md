# backend/ · API del visor SPHEREx

Rol A (Camilo). Python + FastAPI. Plan y estado: [`PLAN.md`](PLAN.md).

## Correr en local

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r backend/requirements.txt
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
| `app/render.py` | Remuestreo a grilla de cielo norte arriba y PNG (`asinh`/`linear`). |
| `app/science.py` | Puente con `core/` (Nacho): objetivos, FLAGS, espectros. |
| `app/main.py` | Endpoints HTTP. |
| `app/precompute.py` | `python -m app.precompute`: deja en caché los objetivos de la demo (#26). |
| `app/release_update.py` | `python -m app.release_update [--apply]`: suma releases nuevos de IRSA (#28). |

## Endpoints (siguen `contracts/api.md` v0)

Parámetros comunes: `target` (`eps_ind_b`, `wise_0855`, `rw_aur`, `r_dra`) **o** `ra`+`dec`
(grados, o sexagesimal `08h55m10.831s` / `-7d14m42.53s`), y `size` en grados (0.1 por defecto, máx. 0.3).
Con `target` el recorte se centra donde está el objeto en 2026 (movimiento propio de `core.targets`).
Los errores son siempre JSON: `{"error": "...", "detail": "..."}` (422 parámetro, 404 cuadro, 501 core
pendiente, 502 IRSA).

| Endpoint | Qué devuelve |
|---|---|
| `GET /api/frames?target=\|ra&dec&size&band&detector&limit&offset` | Cuadros por fecha: `id, mjd, date, detector ("D2"), wavelength_um, bandwidth_um, band, release, image_url, target_xy, flagged_fraction, quality` + `ready, meta_url, collection`. Arriba: `n_frames, n_dates, pending, complete`. |
| `GET /api/frame/{id}/png?…&stretch=asinh\|linear&layer=image\|image-zodi\|variance\|flags&bits=SOURCE,21` | PNG norte arriba en una grilla de cielo fija. |
| `GET /api/frame/{id}/meta?…` | Header + `flags.cutout_counts` (del recorte), `full_frame_counts` (de la exposición entera), `undocumented_bits_present`, `at_target`, `mask_layers`, `quality`, `target`. |
| `GET /api/coverage?…` | Por detector, colección, fecha, época y banda, sin bajar cutouts. |
| `GET /api/targets` | Los 4 objetivos, su centro y cuánto hay en caché. |
| `GET /api/spectrum?…` | Llama a `core.extract_spectrum` + `core.combine`. **501** hasta que exista la tarea 23. |
| `GET /api/lightcurve?…&band=` | Llama a `core.light_curve`. **501** hasta la tarea 23. |

Carga progresiva: `/api/frames` responde al instante y encola lo que falta; el frontend vuelve a
pedir hasta `complete: true`. Los cuadros sin bajar traen `ready: false` y `null` en λ, banda, etc.

### Coordenadas de `target_xy`

Píxeles del PNG devuelto, base 0, **x a la derecha e y hacia abajo** (como un `<canvas>`).
El PNG es una grilla de cielo fija (norte arriba, este a la izquierda) centrada en `query.ra/dec`:
las estrellas quedan quietas y el objetivo se mueve, que es lo que muestra el movimiento (O4).
Por eso `target_xy` cambia de cuadro a cuadro y el frontend debe dibujar la cruz ahí.

### Relación con `core/`

| Backend | core/ (Nacho) |
|---|---|
| `app/science.py` | Único puente: `core.targets`, `core.flags`, `core.extract_spectrum`, `core.datatypes.Frame`. |
| Posición del objetivo por fecha | `core.targets.target_position`, interpolada entre los bordes de la ventana (error < 0.001″, hay test). |
| `flagged_fraction`, `cutout_counts`, `mask_layers` | `core.flags.mask_for(…, "photometry")`, `bit_counts`, `pipeline_counts`. |
| Video | Grilla de cielo norte arriba (`render.py`). `core.align_frames` traslada pero no rota, y cada visita de SPHEREx viene con otro ángulo; queda para restas y fotometría. |

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
cd backend && ../.venv/bin/python -m app.precompute [--only wise_0855] [--list]
```

Usa `config/targets.yaml` (rol C, desde SIMBAD) a través de `core.targets`: cada recorte se centra
donde está el objetivo a mitad de la ventana de SPHEREx (2026-01-12).

## CI

`.github/workflows/backend-tests.yml` corre los tests en cada PR que toque `backend/` o `config/`.
