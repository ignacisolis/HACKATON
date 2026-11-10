# Contrato de la API — v0 (propuesta)

> **Estado: BORRADOR, escrito por Nacho (rol C) el 2026-11-10.**
>
> La tarea 3 del Tablero asigna este contrato a **los tres**, y Camilo es el
> dueño de la API. Esto es una propuesta para tener algo concreto sobre lo que
> discutir, no una decisión tomada. Bruno armó una versión v0 en su carpeta
> `spherex-visor` el 5 de noviembre, pero nunca llegó a GitHub, así que no se
> pudo partir de ella.
>
> **Camilo y Bruno: cambien lo que haga falta.** Lo único que pido que no se
> toque sin avisar son los campos marcados con 🔬, que vienen de `core/` y
> reflejan cómo son los datos de SPHEREx de verdad.

Marcar v1 cuando los tres den el OK. Cierra la tarea 3.

---

## Principios

1. **Las coordenadas de entrada son ICRS en grados.** El frontend acepta también
   `hh:mm:ss` y las convierte antes de llamar.
2. **El backend nunca devuelve la posición de catálogo de un objetivo.** Devuelve
   dónde está el objeto en la fecha de cada cuadro. Para WISE 0855 la diferencia
   es de 21 píxeles: ver [`docs/ciencia.md`](../docs/ciencia.md) sección 1.
3. **Toda longitud de onda viaja con su ancho de banda.** 🔬 La resolución no es
   pareja: R ≈ 40 en D1–D4 y R ≈ 128 en D6. Sin el ancho, el panel de espectros
   dibuja una forma falsa.
4. **Los errores son JSON, nunca HTML.** `{"error": "...", "detail": "..."}`.
5. Todas las fechas en **MJD** (`float`) y además en ISO (`string`), porque el
   MJD sale del FITS y el ISO lo muestra la interfaz.

## Parámetros comunes

| Parámetro | Tipo | Por defecto | Notas |
|---|---|---|---|
| `ra` | float | — | grados ICRS |
| `dec` | float | — | grados ICRS |
| `target` | string | — | alternativa a `ra`/`dec`: `eps_ind_b`, `wise_0855`, `rw_aur`, `r_dra`. Si se usa, el backend aplica movimiento propio 🔬 |
| `size` | float | `0.1` | lado del recorte en grados |
| `band` | int | — | 1 a 102. Omitido = todas |
| `detector` | string | — | `D1`–`D6`. Omitido = todos |

Pasar `target` **o** `ra`+`dec`. Si vienen los dos, gana `target` y la respuesta
lo dice en `resolved_from`.

---

## `GET /api/frames`

Los cuadros que cubren un punto, para armar el video.

### Respuesta

```json
{
  "query": {
    "ra": 133.76010, "dec": -7.24221, "size": 0.1,
    "target": "wise_0855",
    "resolved_from": "targets.yaml + movimiento propio",
    "coord_epoch_applied": "2026-05-14"
  },
  "n_frames": 256,
  "n_dates": 27,
  "frames": [
    {
      "id": "l2b-v20-2025-251/level2_2025W23_2B_0696_1D2",
      "mjd": 60834.788416907,
      "date": "2025-06-08T18:55:19.221",
      "detector": "D2",
      "wavelength_um": 1.5143,
      "bandwidth_um": 0.0366,
      "band": 24,
      "release": "l2b-v20-2025-251",
      "image_url": "/api/frame/<id>/png?stretch=asinh",
      "target_xy": [29.5, 29.5],
      "flagged_fraction": 0.41,
      "quality": "ok"
    }
  ]
}
```

### Campos que importan

- 🔬 **`wavelength_um` es la λ en la posición del objetivo**, no la del recorte ni
  la del detector. En SPHEREx el filtro varía a lo largo del detector, así que
  cada exposición mide el objetivo en una λ concreta. Sale de `WCS-WAVE`.
- 🔬 **`target_xy`** es dónde cae el objetivo en la imagen devuelta. El frontend
  lo necesita para dibujar la cruz, y no es siempre el centro.
- `release` viaja en cada cuadro porque puede haber **varios releases a la vez**
  en el archivo. Es parte de la consideración C1.
- 🔬 `flagged_fraction` se calcula **sobre el recorte**, no con las tarjetas
  `L2 N_*` del header: esas son de la imagen completa de 2040×2040 y en un
  recorte de 29×29 dan números imposibles. Ver `core.flags.pipeline_counts()`.

### Orden y filtrado

Ordenado por `mjd` ascendente. 🔬 **Aviso para el reproductor:** con `band`
fijo hay solo **2 a 6 cuadros** para eps Ind B, WISE 0855 y RW Aur. Para R Dra
hay ~34. Si el usuario fija la banda y el video queda de 3 cuadros, conviene
decírselo en la interfaz en vez de mostrar un video que parece roto.

---

## `GET /api/spectrum`

### Respuesta

```json
{
  "query": {"ra": 133.76010, "dec": -7.24221, "target": "wise_0855"},
  "aperture_px": 2.5,
  "mask_purpose": "photometry",
  "n_points": 102,
  "n_epochs_used": 256,
  "points": [
    {
      "wavelength_um": 1.5143,
      "bandwidth_um": 0.0366,
      "band": 24,
      "flux": 0.3421,
      "flux_err": 0.0180,
      "unit": "MJy/sr",
      "detector": "D2",
      "n_epochs": 3,
      "flagged_fraction": 0.12,
      "quality": "ok"
    }
  ]
}
```

- 🔬 `mask_purpose` **tiene que ser `photometry`** acá. Con `background` el
  resultado es cielo vacío: esa máscara enmascara `SOURCE`, que marca los
  píxeles de la fuente. Medido en un recorte real de R Dra: con la máscara de
  fotometría quedan 790 de 841 píxeles; con la de fondo, **cero**.
- 🔬 `n_epochs` es cuántas visitas se combinaron en ese punto. Es de donde sale
  la mejora de señal/ruido de la consideración C8: **visitas repetidas a la
  misma banda**, no apilar los 6 detectores, que miden λ distintas y no se
  solapan. Ver `docs/ciencia.md` 3.4.
- `quality` es `ok`, `suspect` o `bad`.

### `GET /api/lightcurve`

Mismos parámetros más `band` (obligatorio). Devuelve `{"mjds": [], "flux": [],
"flux_err": []}`. La meta del proyecto ahora dice "video **o series de
tiempo**", y para R Dra, una Mira de ~245 días con 522 días de cobertura, esto
muestra dos ciclos completos.

---

## `GET /api/frame/{id}/meta`

```json
{
  "id": "l2b-v20-2025-251/level2_2025W23_2B_0696_1D2",
  "mjd": 60834.788416907,
  "date": "2025-06-08T18:55:19.221",
  "detector": "D2",
  "release": "l2b-v20-2025-251",
  "exposure_s": 113.5826,
  "wavelength_um": 1.5143,
  "bandwidth_um": 0.0366,
  "wcs": {"crval": [247.08197, 66.89044], "ctype": ["RA---TAN-SIP", "DEC--TAN-SIP"]},
  "flags": {
    "extension_is_mask": true,
    "cutout_counts": [
      {"bit": 21, "name": "SOURCE", "label": "Known source", "pixels": 841, "fraction": 1.0},
      {"bit": 2, "name": "SUR_ERROR", "label": "SUR data handling error", "pixels": 50, "fraction": 0.059}
    ],
    "full_frame_counts": {"OUTLIER": 98707, "TRANSIENT": 19834},
    "undocumented_bits_present": []
  },
  "mask_layers": ["SOURCE", "SUR_ERROR", "TRANSIENT", "OVERFLOW", "PERSIST"]
}
```

- 🔬 `cutout_counts` sale de `core.flags.bit_counts()` y es lo que el panel debe
  mostrar. `full_frame_counts` sale del header y es de la exposición entera: si
  el frontend los mezcla, miente por órdenes de magnitud.
- 🔬 `mask_layers` son los bits presentes en ese recorte, que es lo que tiene
  sentido ofrecer como capas prendibles (C6). No tiene sentido ofrecer las 25.
- 🔬 `undocumented_bits_present` es una alarma: si trae algo, el Explanatory
  Supplement y el header FITS quedaron viejos respecto de los datos.

---

## Lo que `core/` le da al backend

Firmas estables, aunque tres de ellas todavía levanten `NotImplementedError`.
Camilo puede escribir contra esto hoy.

| Función | Estado | Devuelve |
|---|---|---|
| `core.targets.target_position(key, mjd)` | ✅ funciona | `(ra_deg, dec_deg)` |
| `core.flags.bit_counts(capa)` | ✅ funciona | lista para `cutout_counts` |
| `core.flags.mask_for(capa, purpose)` | ✅ funciona | array bool, True = excluir |
| `core.flags.pipeline_counts(header)` | ✅ funciona | `full_frame_counts` |
| `core.flags.cross_check_fits(header)` | ✅ funciona | avisa si un release movió bits |
| `core.is_comparable(a, b)` | ✅ funciona | `(bool, motivo)` |
| `core.align(frames, target_key=...)` | firma | `AlignedCube` |
| `core.subtract(a, b)` | firma, **valida ya** | `(diff, var, usable)` |
| `core.spectrum(frames, target_key=...)` | firma | lista de `SpectrumPoint` |

Los tipos de intercambio (`Frame`, `AlignedCube`, `SpectrumPoint`) están en
[`core/types.py`](../core/types.py) con cada campo comentado. **`Frame` no
incluye la PSF** a propósito: viene sin recortar (~4.9 MB) y es ~99 % del peso
de un cutout.

## Pendiente de acordar

- [ ] ¿El backend devuelve PNG ya estirado, o arrays para que el frontend los estire? Cambia mucho el peso y quién decide el contraste.
- [ ] Nombres de los endpoints y si van versionados (`/api/v1/...`).
- [ ] Cómo se numeran las 102 bandas. Acá se asume `band` de 1 a 102 ordenadas por λ creciente, pero hay que confirmar que coincida con la convención de la misión.
- [ ] Paginación de `/api/frames`: R Dra devuelve 2483 cuadros.
- [ ] Si `/api/subtract` es un endpoint o lo hace el frontend con dos cuadros.
