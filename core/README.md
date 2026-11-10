# `core/` — funciones de ciencia

Rol **C · Ciencia** (Nacho). Acá viven las funciones que hacen cuentas sobre
los datos de SPHEREx: alineación, restas, espectros y posiciones de objetivos.

## La regla de esta carpeta

**Funciones puras: reciben valores, devuelven valores.** Nada de acá abre la
red, lee la configuración del servidor ni sabe que existe una web. El backend
(`backend/`, rol A) las importa y las llama; si una función de `core/` necesita
datos de IRSA, los recibe como argumento.

La única excepción es `fetch_targets.py`, que sí habla con SIMBAD. Es un script
de mantenimiento, no parte de la ruta de ejecución de la web: se corre a mano
cuando hay que actualizar el catálogo.

## Qué hay

| Archivo | Qué es | Estado |
|---|---|---|
| `targets.py` | Posiciones de los objetivos propagadas a cualquier fecha | listo |
| `fetch_targets.py` | Regenera `config/targets.yaml` desde SIMBAD | listo |
| `fetch_coverage.py` | Regenera `config/coverage.yaml` desde IRSA | listo |
| `test_targets.py` | 10 pruebas, incluida la verificación de época | pasan |
| `flags.py` | Decodifica la capa `FLAGS` y aplica las máscaras del documento | listo |
| `test_flags.py` | 35 pruebas: bits, máscaras y cruce con el header FITS | pasan |
| `datatypes.py` | `Frame`, `AlignedCube`, `SpectrumPoint`: la frontera con `backend/` | listo |
| `align.py` | Alineación por WCS con movimiento propio (tarea 21) | **listo** |
| `test_align.py` | 26 pruebas, incluido el criterio de aceptación | pasan |
| `subtract.py` | Resta de imágenes comparables (tarea 22) | firmas, valida ya |
| `spectrum.py` | Extracción y combinación de espectros (tarea 23) | firmas |

El notebook de exploración de la Fase 0 está en
[`fase0_spherex_explorar_fits.ipynb`](fase0_spherex_explorar_fits.ipynb), en esta
misma carpeta.

> **Nota sobre `spherex_espectros.py`:** el README principal y la tarea 5 del
> Tablero dan por hecho que ese módulo ya existe y fue probado con datos
> sintéticos. No existe: no está en el repo ni en ningún commit del historial.
> Hay que escribirlo, y se va a escribir partido en `align.py`, `subtract.py` y
> `spectrum.py`, que es como lo pide el Tablero (`core.align()`,
> `core.subtract()`, `core.spectrum()`).

## Instalación

```bash
pip install -r requirements.txt
```

Para graficar espectros más adelante hará falta `matplotlib`. `astroquery` no
se usa: su resolución de nombres apunta a hosts de SIMBAD que no responden
desde la red del equipo (ver [`docs/ciencia.md`](../docs/ciencia.md), sección 2).

## Uso

### Dónde apuntar para un objetivo en una fecha dada

Esto es lo que el backend necesita antes de pedir un recorte a IRSA:

```python
import core.targets as t

# El MJD sale del header de la exposición.
ra, dec = t.target_position("wise_0855", 61174.0)
# -> (133.7589..., -7.2421...)
```

Nunca uses las coordenadas del enunciado directamente. Para WISE 0855 están a
**21.4 píxeles** de donde está el objeto en la era SPHEREx, y el recorte sale
lleno de estrellas que no son el objetivo.

### Alinear una serie de épocas

```python
from astropy.coordinates import SkyCoord
import astropy.units as u

ra, dec = t.target_position("wise_0855", mjd_de_la_exposicion)
x, y = wcs.world_to_pixel(SkyCoord(ra * u.deg, dec * u.deg))
```

### Interpretar la capa FLAGS

```python
import core.flags as f

f.decode(valor)                     # ['SOURCE', 'HOT']
f.mask_for(capa, "photometry")      # True donde hay que EXCLUIR el píxel
f.good_pixels(capa, "background")   # el complemento
f.bit_counts(capa)                  # qué flags hay y en qué fracción (C6)
```

`mask_for()` **exige** el propósito, sin valor por defecto, porque el documento
da dos listas distintas y elegir mal cambia el resultado en silencio:
`SOURCE` (bit 21, ~41 % de los píxeles) se enmascara para estimar el **fondo**
pero **nunca** para **fotometría** — ahí marca los píxeles de la fuente que se
quiere medir.

```bash
python core/flags.py        # imprime la tabla de bits y las dos máscaras
```

### Objetivos disponibles

```python
t.target_keys()              # ['eps_ind_b', 'wise_0855', 'rw_aur', 'r_dra']
t.needs_pm_correction("r_dra")   # False
t.summary_rows()             # tabla para docs y presentación
```

### Actualizar el catálogo

```bash
python core/fetch_targets.py              # reescribe config/targets.yaml
python core/fetch_targets.py --dry-run    # solo muestra qué quedaría
```

## Pruebas

```bash
python core/test_targets.py     # 10 pruebas de astrometría
python core/test_flags.py       # 35 pruebas de FLAGS
python core/test_align.py       # 26 pruebas de alineación
```

O con pytest, si está instalado: `pytest core/`.

La prueba que importa es `test_wise0855_epoch_is_j2000`. Verifica que las
coordenadas de SIMBAD están a época J2000 propagándolas hasta 2010.5 y
comparándolas con las que lleva codificadas el nombre `WISE J085510.83-071442.5`.
Da **0.41″** de diferencia, cuando un año de error de época daría 8.15″.

Si esa prueba se rompe, no toques el umbral: significa que cambió algo en la
fuente de datos y todas las posiciones del proyecto quedaron en duda.
