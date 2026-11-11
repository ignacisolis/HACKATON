# frontend/ — Bruno · B · Frontend y experiencia

Leé primero el `AGENTS.md` de la raíz. Esta carpeta es de **Bruno** (rama `front`). Si trabajás con
otra persona, no edites acá: pedilo en la Bitácora. Cómo correrla: `README.md` de esta carpeta.

## Qué entrega

La web pública: coordenadas → video del cielo en el tiempo, detector y banda, vista compartible por
URL, metadata y capas de FLAGS, resta de cuadros, espectro y curva de luz, Aladin Lite. Además Bruno
la despliega (`.github/workflows/frontend.yml`).

## Reglas de la carpeta

1. **Ningún componente hace `fetch`.** Todo pasa por `api` en `src/api/client.ts`, que decide entre
   backend real y fixtures (`VITE_USE_FIXTURES=1`). Los tipos del contrato viven en
   `src/api/types.ts`: si el contrato cambia, se cambian ahí y en ningún otro lado.
2. **La vista es la URL** (`src/state/view.tsx`, C4): `target` o `ra`/`dec`, `fov`, `det`, `band`,
   `t`, `stretch`, `zodi`, `mask`, `diff`, `pra`/`pdec`, `lang`. Lo efímero (hover, play) es estado
   local del componente.
3. **Los cuadros se piden una vez por vista** en `src/state/frames.tsx` (con sondeo mientras el
   backend baja de IRSA) y los comparten todas las áreas por `useFrames()`.
4. **Un área, una carpeta** en `src/features/` (`nav`, `player`, `inspect`, `science`), que entra a
   la página por un solo componente en `App.tsx`. Cada área trae su `i18n.ts` (claves `<área>.*`) y
   su CSS usando solo las variables de `src/index.css`.
5. **Inglés y español** siempre: hay un test que falla si una clave falta en un idioma.
6. **Lógica pura en `.ts` con pruebas** (vitest), componentes finos. Antes de cerrar:
   `npx tsc -b && npx vitest run && npx vite build`.
7. Si al frontend le falta un campo, **se pide con un PR a `contracts/`**, no se calcula en el
   navegador. Pendiente hoy: `/api/diff` y `display_range` (PR `bruno/contrato-front`).

## Lo que el dominio le impone a la interfaz

- **Píxeles nítidos** (`image-rendering: pixelated`): un píxel de SPHEREx son 6.2″; suavizar inventa
  detalle.
- **Sin banda fija, el video toma un cuadro por fecha** con la λ más parecida dentro del detector
  (`features/player/sequence.ts`): cada exposición cae en otro canal y, mezcladas, el brillo cambiaría
  por color y no por el objeto. Una banda se elige **siempre dentro de un detector** (las bandas se
  solapan en las costuras).
- **Pocos cuadros por banda** (2–6 en 3 de los 4 objetivos): se avisa en vez de mostrar un video que
  parece roto.
- **La resta solo vale entre cuadros comparables** (mismo detector, |Δλ| ≤ ½ ancho de banda). Si el
  backend responde 422, se muestra su motivo. El movimiento de WISE 0855 (~1.35 px en la ventana) se
  ve con resta en D5–D6, no en el video.
- **R Draconis satura**: buen video (222 fechas), pero su flujo y su espectro no son confiables.
  Variabilidad y espectros se muestran con **RW Aurigae**.
- **Epsilon Indi B** no se ve como dos puntos (0.72″ contra 6.2″). No prometerlo.
- **`cutout_counts` y `full_frame_counts` no se mezclan**: el segundo es de la exposición entera.
- Hoy cada PNG se estira por separado: en las variables eso aplana el cambio de brillo. Se arregla
  cuando el backend dé `display_range`.
- Aladin carga los HiPS desde el espejo de IRSA: los servidores alasky de CDS no respondían desde
  nuestra red.

## Con quién te cruzás

- **Camilo** te da la API (`backend/`) y mergea a `main`.
- **Nacho** define la ciencia: si un texto de la interfaz afirma algo científico, tiene que salir de
  `docs/ciencia.md` o de `core/`.
