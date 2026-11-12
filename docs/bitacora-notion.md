# Cómo se registra el avance en Notion

## Dónde está

Notion → **LufkeyW — Espacio de trabajo** → **Hackathon NASA · SPHEREx**

| Qué | Para la IA (conector de Notion) | Link |
|---|---|---|
| Página de la sección | `40ff332645cd81e5af5bd77a14542511` | https://app.notion.com/p/40ff332645cd81e5af5bd77a14542511 |
| **Tablero SPHEREx** | data source `collection://cadb7cc4-4827-45b1-9211-1e24c78649bc` | https://app.notion.com/p/12b60357f1d74d24a962ce0aeafeb614 |
| **Bitácora SPHEREx** | data source `collection://375aab64-9e99-443e-8876-2389f85f02a7` | https://app.notion.com/p/6d7bd37960934ddcafb66079012cb849 |

El workspace está en el **plan gratis con poco espacio de bloques**. Por eso: filas de base de
datos, solo columnas, **nada de texto dentro de las páginas**. El detalle va en el repo.

## Tablero: una fila por tarea

Columnas: `Tarea` (título), `ID` (número automático: "tarea 15"), `Responsable` (Bruno, Camilo,
Nacho, Todos), `Rol`, `Carpeta`, `Fase` (0 · Preparación … 6 · Presentación), `Prioridad`
(Imprescindible, Muy valioso, Extra), `Estado`, `Listo cuando`, `Depende de`.

`Estado` va así:

```
Por hacer ──► En curso ──► En revisión ──► Hecho
                 │              │
             Bloqueado      PR a main abierto; Hecho = mergeado y cumple "Listo cuando"
```

Cada uno mueve **solo sus tareas**. Una tarea sin `Listo cuando` no se empieza.

## Bitácora: una fila por sesión

Al cerrar cada sesión de trabajo, **una fila**, aunque la tarea no esté terminada.

| Columna | Qué va | Ejemplo |
|---|---|---|
| `Avance` (título) | Una línea, lo que quedó hecho | Reproductor con play/pausa contra fixtures |
| `Fecha` | Hoy | 2026-11-11 |
| `Quién` | Bruno, Camilo o Nacho | Bruno |
| `Rol` | A · Datos y backend / B · Frontend / C · Ciencia / Integración | B · Frontend |
| `Hice` | 1–3 frases concretas | Player lee /api/frames, muestra fecha/detector/λ, velocidad 1–12 fps |
| `Sigue` | Lo próximo | Panel de espectro |
| `Bloqueos` | Qué me frena, con el NOMBRE en mayúsculas de a quién se lo pido | CAMILO: falta /api/diff |
| `Necesito de` | Nadie / Bruno / Camilo / Nacho / Todos | Camilo |
| `Rama o commit` | Rama y hash corto (y PR si hay) | `front @ 1e410d0 · PR #3` |
| `Tareas` | Relación a las tareas del Tablero que tocó | tareas 14, 15 |

**Leer antes de escribir**: al empezar una sesión, la IA lee las últimas 5 filas de los tres. Si hay
un `Necesito de` con tu nombre, se atiende primero.

## Si tu IA no tiene conector de Notion

Que imprima la fila así y la pegás a mano:

```
Avance:        <una línea>
Fecha:         <AAAA-MM-DD>
Quién:         <Bruno|Camilo|Nacho>
Rol:           <A · Datos y backend|B · Frontend|C · Ciencia|Integración>
Hice:          <1–3 frases>
Sigue:         <próximo paso>
Bloqueos:      <o vacío>
Necesito de:   <Nadie|Bruno|Camilo|Nacho|Todos>
Rama o commit: <rama @ hash>
Tareas:        <tarea n, tarea m>
```

## Para una IA con conector: cómo escribir

- **Fila de Bitácora**: crear una página en el data source de la Bitácora con estas propiedades
  (nombres exactos): `Avance`, `date:Fecha:start` (AAAA-MM-DD), `date:Fecha:is_datetime` (0),
  `Quién`, `Rol`, `Hice`, `Sigue`, `Bloqueos`, `Necesito de`, `Rama o commit`, `Tareas` (array JSON
  con las URLs de las tareas del Tablero). **Sin `content`.**
- **Mover una tarea**: actualizar la propiedad `Estado` de su página en el Tablero a `Por hacer`,
  `En curso`, `En revisión`, `Bloqueado` o `Hecho`.
- **Leer**: consulta SQL sobre el data source, por ejemplo las últimas filas de la Bitácora ordenadas
  por `createdTime DESC`, o las tareas con `"Responsable" IN ('Bruno', 'Todos')`.
- Reemplazar páginas enteras falla con el límite de bloques; editar propiedades funciona.
