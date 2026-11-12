# Equipo y reparto de roles

Proyecto: **Visor web de SPHEREx — el cielo en el tiempo**
Repositorio: https://github.com/ignacisolis/HACKATON

Roles **confirmados** el 2026-11-10. Cierra la tarea 2 del
[Tablero SPHEREx](https://app.notion.com/p/12b60357f1d74d24a962ce0aeafeb614).

---

## Reparto

| Rol | Persona | Rama | Carpeta | Es dueño de |
|---|---|---|---|---|
| **A · Datos y backend** | **Camilo** | `back` | `backend/` | Acceso a IRSA, caché, API, configuración de versiones, script de actualización, despliegue del backend |
| **B · Frontend y experiencia** | **Bruno** | `front` | `frontend/` | Formulario, reproductor, selector de banda, coordenadas en la URL, panel de espectro, capa de máscaras, Aladin, despliegue de la web |
| **C · Ciencia y procesamiento** | **Nacho** | `ciencias` | `core/` | Alineación, imagen de referencia, restas, espectros, combinación de detectores, validación con los 4 objetivos, documentación |

**Integración:** Camilo. Es quien mergea a `main` y quien resuelve los choques
entre carpetas.

## Cómo trabajamos

1. Cada uno trabaja **solo en su carpeta y en su rama**. Nadie commitea en `main`.
2. Lo que se pasa entre carpetas va en `contracts/api.md`. Si algo cambia ahí, se avisa a los otros dos antes de mergear.
3. `core/` entrega **funciones puras** (reciben arrays, devuelven arrays) que `backend/` llama. `core/` no abre la red ni sabe que existe una web.
4. `frontend/` trabaja contra `contracts/fixtures/` desde el día uno, sin esperar al backend real.
5. Al terminar una sesión de trabajo: **una fila en la [Bitácora](https://app.notion.com/p/6d7bd37960934ddcafb66079012cb849)** y el Estado de la tarea al día en el Tablero.
6. Sincronización breve 2 o 3 veces por semana.

## Dependencias entre roles

Quién espera a quién, para no bloquearse:

| Lo que falta | Lo bloquea | A quién |
|---|---|---|
| `contracts/api.md` v1 | las tres partes | los tres, primera sync |
| `config/targets.yaml` | precálculo de los 4 objetivos | Camilo ✅ ya está |
| `config/flags.yaml` | `/api/frame/{id}/meta` y la capa de máscaras | Camilo y Bruno ✅ ya está |
| `core.spectrum()` | `GET /api/spectrum` | Camilo |
| `GET /api/spectrum` | panel de espectro | Bruno |
| `GET /api/frames` | reproductor con datos reales | Bruno |

## Kit de herramientas

Qué instala cada uno, con qué servicios habla y las trampas ya documentadas:
**sección 8.1 del [README](../README.md)**.

## Pendientes de equipo

- [x] **Fecha límite del hackathon: 15 de noviembre de 2026.** Está en el README.
- [x] **Stack confirmado** (tarea 1): `core/` y `backend/` en Python con FastAPI; `frontend/` en Vite + React + TypeScript. Detalle en `AGENTS.md`.
- [x] **Nombre del proyecto: HackatonNASA** (tarea 1).
- [x] **`contracts/api.md` v1** con el OK de los tres (tarea 3).
- [x] Reparto de roles confirmado.
- [x] Repo en GitHub con una rama por persona.
