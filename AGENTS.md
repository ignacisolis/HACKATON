# AGENTS.md — reglas para cualquier IA que trabaje en este repo

Lo leen Claude Code (vía `CLAUDE.md`), Codex, Cursor, Copilot y Gemini. **Si sos una IA ayudando a
alguien del equipo, leelo entero antes de tocar nada**, y después el `AGENTS.md` de la carpeta donde
vas a trabajar (`core/AGENTS.md`, `frontend/AGENTS.md`, …).

## El proyecto en tres líneas

Visor web público de **SPHEREx** (NASA) para la hackathon, con **entrega el 15 de noviembre de 2026**.
El usuario escribe RA/Dec o elige uno de 4 objetivos y ve esa zona del cielo como **video en el
tiempo**: elige detector y banda, comparte la vista por URL, resta cuadros, mira máscaras y espectros.
Contexto completo en `README.md`; hallazgos científicos y sus fuentes en `docs/ciencia.md`.

## Quién es dueño de qué (roles confirmados el 2026-11-10)

| Persona | Rol | Es dueño de | Rama |
|---|---|---|---|
| **Camilo** | A · Datos y backend + **integración** | `backend/`, `config/release.yaml`, despliegue del backend | `back` |
| **Bruno** | B · Frontend y experiencia | `frontend/`, `.github/workflows/frontend.yml`, despliegue de la web | `front` |
| **Nacho** | C · Ciencia y procesamiento | `core/`, `config/targets.yaml`, `config/flags.yaml`, `config/bands.yaml`, `config/coverage.yaml`, `docs/ciencia.md` | `ciencias` |
| Los tres | — | `contracts/`, `docs/EQUIPO.md`, `docs/bitacora-notion.md`, este archivo | PR propio con el OK de los tres |

Camilo es el integrador: revisa y mergea a `main`. Nadie commitea directo en `main`.

### Reglas que no se rompen

1. **No editar la carpeta de otro.** Si necesitás algo de otra carpeta, pedilo en la Bitácora
   (`Necesito de`) y seguí con fixtures o con otra tarea.
2. **El contrato manda.** Lo que se pasa entre carpetas está en `contracts/api.md`. Frontend y
   backend se hablan **solo** por esa API; backend llama a `core/` **solo** por las funciones de la
   tabla "Lo que `core/` le da al backend". Un cambio de contrato va en un PR aparte que toca **solo**
   `contracts/` (ejemplo: `bruno/contrato-front`), y no se usa hasta que los tres lo aprueben.
3. **Los fixtures son el contrato ejecutable.** `contracts/fixtures/*.json` es lo que el frontend usa
   sin backend (`VITE_USE_FIXTURES=1`) y lo que `backend/tests/test_contract.py` compara con las
   respuestas reales. Si cambia el contrato, cambia el fixture en el mismo PR.
4. **`core/` es ciencia pura**: funciones que reciben arrays y devuelven arrays o diccionarios. Sin
   red, sin disco, sin FastAPI (salvo los scripts de mantenimiento `fetch_*.py` y `validate_*.py`).
5. **Todo acceso a IRSA vive en `backend/app/irsa.py`.** El frontend nunca habla con IRSA directo.
6. **Nada inventado.** Un dato científico no verificado (coordenadas, movimiento propio, significado
   de un bit de FLAGS) se marca `# por verificar` en el código y en el texto. Antes de dar un número
   por bueno, leé "Antes de dar un número por bueno" en `core/AGENTS.md`.
7. **Nunca commitear** FITS, cachés (`cache/`), `.venv/`, `node_modules/`, `.env*.local` ni
   credenciales.

## Cómo trabaja una sesión de IA acá

Toda sesión tiene **inicio, trabajo y cierre**. El cierre no es opcional: es lo que permite que los
otros dos sepan en qué estás sin preguntarte.

### Inicio (antes de escribir código)

1. Preguntá con quién estás trabajando si no lo sabés (Bruno, Camilo o Nacho).
2. Leé `docs/EQUIPO.md` y el `AGENTS.md` de su carpeta.
3. Leé en Notion **sus tareas** del Tablero (`Responsable` = esa persona, o `Todos`) y **las últimas
   5 filas de la Bitácora de los tres**. Si alguien le pidió algo (`Necesito de`), eso va primero.
   IDs y formato en `docs/bitacora-notion.md`.
4. Mirá los PR abiertos (`gh pr list`): puede haber algo para revisar o un pedido de contrato.
5. Proponé **una** tarea para la sesión (la de menor fase que no esté bloqueada) y un plan corto.
   Cuando la persona acepte, pasala a `En curso` en el Tablero.

### Trabajo

- En la rama de la persona (`front`, `back` o `ciencias`), actualizada con `git pull`. Para un cambio
  de contrato o de archivos de los tres, una rama aparte desde `main` (`<persona>/<tema>`).
- Commits chicos, en español, que digan qué cambió y por qué.
- Si te bloqueás por otro: tarea en `Bloqueado`, pedido en la Bitácora, y seguí con fixtures o con
  otra tarea.

### Cierre (siempre, aunque la tarea no esté terminada)

1. Commit y push a la rama propia.
2. **Una fila en la Bitácora** de Notion con el formato de `docs/bitacora-notion.md`. Sin conector de
   Notion, imprimí la fila en ese formato para que la persona la pegue.
3. `Estado` de la tarea al día. Si cumple su `Listo cuando`, PR a `main` con la plantilla y la tarea
   pasa a `En revisión`.

**Notion es el registro corto; el detalle va en el repo.** El workspace está en el plan gratis con
poco espacio de bloques: una fila por sesión, solo columnas, sin texto dentro de la página.

## Stack (confirmado)

| Carpeta | Stack | Cómo se corre |
|---|---|---|
| `core/` | Python 3.11+, numpy, astropy, pyyaml | `pip install -r requirements.txt`; pruebas con `pytest core` |
| `backend/` | Python 3.11+, FastAPI, httpx, scipy, pillow | `uvicorn app.main:app --app-dir backend --port 8000` (ver `backend/README.md`) |
| `frontend/` | Vite + React + TypeScript, Aladin Lite | `cd frontend && npm install && npm run dev` (ver `frontend/README.md`) |

El CI (`.github/workflows/`) corre las pruebas de `core/`, del backend y del frontend en cada push a
`front`, `back`, `ciencias` y en cada PR a `main`.

## Lo que ya aprendimos de los datos (resumen; detalle en `docs/ciencia.md`)

- **Movimiento propio**: las coordenadas del enunciado de WISE 0855 son de ~2010. Usar `target=` en
  la API (aplica movimiento propio) o se mide cielo vacío. Dentro de la ventana de datos WISE 0855 se
  mueve solo ~1.35 px: el movimiento se demuestra con **resta**, y en D5–D6, donde el objeto domina.
- **No se restan cuadros de distinta λ.** Cada exposición mide el objetivo en un canal distinto; la
  λ en el objetivo sale de `WCS-WAVE`, no del TAP. `core.is_comparable()` decide.
- **Las bandas se solapan en las costuras entre detectores**: una banda se elige siempre dentro de un
  detector.
- **R Draconis satura** (BLOOM y HALO): es el mejor caso para el video por sus 222 fechas, pero no
  admite fotometría ni espectro. **RW Aurigae** es el caso para variabilidad y espectros.
- **Epsilon Indi B**: las dos enanas (0.72″) caen en un píxel de 6.2″. No se prometen dos puntos.
- **Bit 21 de FLAGS es `SOURCE`**, la máscara de fuentes, no un defecto.
- IRSA da **HTTP 503** tras muchas descargas seguidas: reintentos con espera, y precalcular los 4
  objetivos. Los servidores de imágenes de CDS (alasky) pueden no responder: el frontend usa el
  espejo de HiPS de IRSA para Aladin.
