# Propuesta de cambios al contrato — Bruno (rol B), 2026-11-11

> Para un PR que toca **solo** `contracts/`. Cuando Camilo y Nacho den el OK, esto se integra a
> `api.md` y se borra este archivo. Hasta entonces el frontend ya maneja los dos casos (con y sin
> estos cambios) sin romperse.

## 0. OK al contrato v0

Doy el OK a `contracts/api.md` v0 **con las decisiones del backend (1–10)**, que el frontend ya usa:
`id` sin barra, `/png` estirado en el backend, grilla norte arriba con `target_xy` por cuadro,
`ready`/`pending`/`complete` para la carga progresiva y `limit`/`offset`.

El frontend **siempre manda `detector` junto con `band`**: las bandas se solapan en las costuras
entre detectores (Nacho, Bitácora del 10/11), así que una banda sola no identifica nada.

## 1. Nuevo: `GET /api/diff` — resta de dos cuadros (C5, O4)

Los PNG llegan estirados, así que restarlos en el navegador no tiene sentido físico. La resta tiene
que hacerse en MJy/sr, en el backend, con `core.subtract_frames` (o `subtract_aligned`) de Nacho.

```
GET /api/diff?a=<id>&b=<id>&(target=… | ra=…&dec=…)&size=0.1[&vmax=…]
```

- Respuesta: **PNG** de `a − b` en la misma grilla de cielo norte arriba que `/png` (mismo tamaño,
  así la cruz de `target_xy` vale igual). Escala **divergente simétrica** alrededor de 0
  (`[-vmax, +vmax]`, gris medio = 0), así el dipolo positivo/negativo de un objeto en movimiento se lee
  de un vistazo. `vmax` por defecto: percentil 99.5 de `|a − b|`.
- **422** `{"error": "not_comparable", "detail": "<motivo de core.is_comparable>"}` si no se
  pueden restar (distinto detector, λ fuera de tolerancia, distinta forma).
- **404** si algún id no existe (igual que `/png`).
- Opcional, si sale barato: header `X-Dipole-SNR` con `core.dipole_snr(diff, var)`, para que la
  interfaz diga "movimiento detectado (S/N = …)".

Fixture: no hace falta un JSON; alcanza con un test que pida `/api/diff` de dos cuadros
comparables de WISE 0855 y valide 200 + `image/png`, y uno de detectores distintos que valide 422.

## 2. Nuevo campo en cada cuadro de `/api/frames`: `display_range` (importante para las variables)

Hoy, si no se pasan `vmin`/`vmax`, cada PNG se estira con su propio ZScale. Eso es correcto para un
cuadro suelto, pero **en un video normaliza cada cuadro por separado y borra justo lo que queremos
mostrar**: el cambio de brillo de RW Aurigae y R Draconis (O5). Además hace parpadear el fondo.

Propuesta: cada cuadro `ready` trae los límites que el backend habría usado, en MJy/sr:

```json
"display_range": { "zscale": [0.12, 0.58], "p99_7": 3.4 }
```

El frontend junta los de la secuencia (mediana de los mínimos, máximo de los máximos, por
detector) y pide **todos** los `/png` con el mismo `vmin`/`vmax`, que el endpoint ya acepta. Así el
brillo del objeto cambia de verdad entre cuadros. Mientras no exista el campo, el frontend sigue con
el estirado por cuadro y muestra un aviso en las variables.

## 3. Aclaraciones (no cambian nada, solo para dejarlas escritas)

- `/api/frames` se pide **filtrado por `detector`** (y por `band` si el usuario la fija): así el
  backend encola solo lo que se va a mostrar, y R Draconis no dispara 2476 descargas.
- El video por defecto usa **un detector con todas sus bandas**, eligiendo el de más fechas según
  `/api/coverage`.
- Para el espectro de un punto clickeado, el frontend llama `/api/spectrum?ra=&dec=` (sin
  `target`), o sea sin movimiento propio. Es lo esperable para un punto arbitrario.
