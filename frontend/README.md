# frontend/ · la web del visor SPHEREx

Rol B (Bruno). Vite + React + TypeScript, sin librerías de UI ni de gráficos (salvo Aladin Lite).
Interfaz en inglés y español (`?lang=en|es`).

## Correr en local

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173 — /api va por proxy al backend en :8000
```

El backend se levanta aparte (ver `backend/README.md`). Para usar el backend público en vez del
local, crear `frontend/.env.development.local` (no se commitea) con
`VITE_API_BASE=https://spherex-api.onrender.com`. Tiene que ser `.env.development.local`:
`.env.local` pierde contra `.env.development`. Sin backend, con datos de prueba:

```bash
VITE_USE_FIXTURES=1 npm run dev
```

Pruebas y build:

```bash
npm test               # vitest
npx tsc -b             # tipos
npm run build          # dist/ listo para publicar
```

## Variables

| Variable | Qué hace |
|---|---|
| `VITE_USE_FIXTURES=1` | Usa `contracts/fixtures/` en vez del backend. Los flujos son inventados: la interfaz lo avisa. |
| `VITE_API_BASE` | URL del backend. Vacía = mismo origen (en dev, proxy de Vite a `:8000`). |
| `VITE_BASE` | Ruta pública del sitio (`/HACKATON/` en GitHub Pages). |
| `VITE_PROXY_TARGET` | A dónde manda el proxy de dev (por defecto `http://localhost:8000`). |

## Cómo está armado

```
src/
  api/        types.ts (el contrato en TypeScript), client.ts (ÚNICO acceso a datos), fixtures.ts
  state/      view.tsx (la vista = la URL, C4) · frames.tsx (cuadros compartidos, carga progresiva)
  lib/        sky.ts (píxel ↔ RA/Dec, formatos sexagesimales)
  i18n/       index.ts + common.ts; cada área trae su diccionario
  features/
    nav/      coordenadas, objetivos, enlaces a SIMBAD/Aladin, Aladin Lite embebido
    player/   video: escenario, controles, detector y banda, secuencia
    inspect/  metadata, capas de máscara FLAGS, resta de cuadros
    science/  espectro instantáneo y curva de luz
```

Reglas:

- **Ningún componente hace `fetch`**: todo pasa por `api` en `src/api/client.ts`, que sabe si va al
  backend o a los fixtures.
- **Lo que define la vista va en la URL** (`state/view.tsx`): objetivo o RA/Dec, `fov`, `det`,
  `band`, `t`, `stretch`, `zodi`, `mask`, `diff`, `pra`/`pdec`, `lang`. Un link reproduce la vista.
- Cada área es dueña de su carpeta en `features/` y entra a la página por un solo componente
  (`App.tsx`). Textos con `useT()` y claves `<area>.*`; hay un test que exige las dos lenguas.

## Lo que depende del backend (ver `contracts/propuesta-front-2026-11-11.md`)

- **Resta** (`/api/diff`): propuesta a Camilo. Hasta que exista, el panel lo avisa.
- **Contraste común** (`display_range` por cuadro): sin eso cada PNG se estira solo y el video
  aplana el cambio de brillo de las variables.
- **Espectro y curva de luz**: necesitan las funciones de la rama `ciencias` mergeadas en `back`.

## Publicación

`.github/workflows/frontend.yml` corre tipos, pruebas y build en cada push a `front` y PR a `main`,
y publica en GitHub Pages al entrar a `main`. **El repo es privado**: Pages en repos privados pide
un plan pago. Mientras no se defina, el job de publicación va a fallar.
