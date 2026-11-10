# Notas de ciencia · rol C

Lo que el resto del equipo necesita saber del lado científico, y de dónde sale
cada número. Mantiene esta página el rol C (Nacho).

Estado: **tareas 6, 7 y 8 cerradas.** Toda la Fase 0 del rol C está lista.

---

## 1. Astrometría de los 4 objetivos (tarea 6)

El dato vive en [`config/targets.yaml`](../config/targets.yaml), que se
**regenera** con `python core/fetch_targets.py`. No editarlo a mano.

| Objetivo | SIMBAD `main_id` | Tipo | pm (″/año) | Dist. (pc) | Deriva J2000→2026 | Corrección |
|---|---|---|---|---|---|---|
| Epsilon Indi B | `* eps Ind B` | BD* (T1V+T6V) | 4.684 | 3.69 | 125.3″ = **20.2 px** | **requerida** |
| WISE 0855 | `WISEA J085510.74-071442.5` | BD* (Y2) | 8.152 | 2.28 | 218.1″ = **35.2 px** | **requerida** |
| RW Aurigae A | `V* RW Aur A` | Or* (K6) | 0.0275 | 156.1 | 0.74″ = 0.12 px | no hace falta |
| R Draconis | `V* R Dra` | Mi* (M4.5-6+e) | 0.0215 | 799.4 | 0.58″ = 0.09 px | no hace falta |

Fuente de todos los valores: SIMBAD, tabla `basic`, vía TAP. Los bibcodes por
objeto están en el YAML (`sources`). En resumen: Gaia EDR3
(`2020yCat.1350....0G`) para eps Ind B, RW Aur A y R Dra; Kirkpatrick et al.
2021 (`2021ApJS..253....7K`) para WISE 0855.

### 1.1 El movimiento propio no es un detalle

Las coordenadas que da el enunciado para WISE 0855 (`08h55m10.831s`,
`-07d14m42.53s`) son las de su **designación WISE**, o sea la posición en la
época de descubrimiento, ~2010.5. En la ventana de SPHEREx el objeto ya está
**132.9″ = 21.4 píxeles** de ahí.

> Ojo con no leer esto de más: esos 21 píxeles separan las coordenadas de 2010 de
> la posición actual. **No** es lo que el objeto se mueve mientras SPHEREx lo
> observa, que es solo 1.35 px. Ver sección 3.2.

Apuntar a las coordenadas del enunciado no da un error visible: da un recorte
de cielo que parece normal, lleno de otras fuentes, sin el objetivo. Es el tipo
de error que sobrevive hasta la presentación.

Lo mismo con eps Ind B: 20 píxeles de deriva. Para RW Aur y R Dra la
corrección es irrelevante (menos de un cuarto de píxel en 26 años), pero el
código la aplica igual porque no cuesta nada.

### 1.2 Cómo se verificó la época

Todo esto depende de una suposición: que las coordenadas de SIMBAD están a
época **J2000.0**. Si fuera falsa, apuntaríamos mal y no lo notaríamos.

La prueba `test_wise0855_epoch_is_j2000` en
[`core/test_targets.py`](../core/test_targets.py) la verifica sin creerle a
nadie: propaga la posición J2000 de SIMBAD hasta 2010.5 y la compara con las
coordenadas codificadas en el nombre `WISE J085510.83-071442.5`.

**Resultado: 0.41″ de diferencia.** Un año de error de época daría 8.15″, así
que el margen no deja lugar a dudas. La suposición es correcta.

### 1.3 Dos trampas de nomenclatura

Las dos costaron tiempo y las dos rompen la demo en silencio:

- **`* eps Ind B` (mayúscula) ≠ `* eps Ind b` (minúscula).** La mayúscula es el
  par de enanas cafés T1V+T6V que pide el enunciado. La minúscula es el
  planeta del sistema, otro objeto en otra posición.
- **`V* RW Aur A` ≠ `V* RW Aur`.** Usamos la entrada `A`, con astrometría de
  Gaia (error de posición 0.037″). La entrada del sistema tiene 3.3″ de error y
  una paralaje de Hipparcos de 15.42 mas que es **incompatible** con la de Gaia
  (6.41 mas): 65 pc contra 156 pc. La de Gaia es la buena; RW Aur está en Tauro,
  a ~156 pc.

### 1.4 Qué se va a ver, y qué no

| Par | Separación | A 6.2″/píxel |
|---|---|---|
| eps Ind A ↔ B | 402.5″ | **65 px: separados** |
| eps Ind Ba ↔ Bb | 0.72″ | 0.12 px: mezclados |
| RW Aur A ↔ B | ~1.4″ | 0.23 px: mezclados |

Conclusión para la demo: **eps Ind B se puede medir sin la contaminación de la
estrella A**, que está a 65 píxeles. Pero las dos enanas del par B salen como
un solo punto, igual que RW Aur A y B. No prometer "ver las dos enanas".

### 1.5 Dudas que quedan abiertas

- **La paralaje de R Dra (1.2509 mas → 799 pc) es sospechosa.** Las Mira tienen
  fotocentros variables y radios enormes, y Gaia suele medirlas mal. La
  literatura la ubica más cerca. No afecta a este proyecto, porque solo usamos
  su posición y su movimiento propio es despreciable, pero no citar esa
  distancia como un dato firme en la presentación.
- La corrección por **aceleración de perspectiva** (que el movimiento propio
  cambie porque el objeto se acerca) está implementada vía `distance_pc` y
  `radial_velocity_km_s`, pero para eps Ind el efecto acumulado en 26 años es
  de ~0.02″, muy por debajo de un píxel. No es un riesgo.

---

## 2. Acceso a la red: SIMBAD sí funciona

El README principal y la Bitácora anotan que *"SIMBAD no respondió desde
nuestra red"* y dejan las coordenadas como pendiente. **El problema no era la
red.** Lo que pasa es esto:

| Host | Resultado |
|---|---|
| `simbad.u-strasbg.fr` | **no resuelve por DNS**, el host ya no existe |
| `simbad.cds.unistra.fr` | falla el TLS: `CERTIFICATE_VERIFY_FAILED` con el almacén de certificados por defecto de Python; y su endpoint TAP devuelve 404 |
| `simbad.harvard.edu` | **funciona**, ~0.5 s por consulta |
| `irsa.ipac.caltech.edu/TAP` | funciona, pero lento: ~16 s la primera consulta |

Receta: usar el mirror de Harvard y pasarle el bundle de `certifi` al contexto
SSL. Son tres líneas, están en `tap_query()` dentro de
[`core/fetch_targets.py`](../core/fetch_targets.py).

Esto también explica por qué Sesame daba timeouts: `astroquery` apunta por
defecto a los hosts de Estrasburgo.

**Implicación para el backend (rol A):** 16 s de latencia en IRSA confirma que
la caché y el precálculo de los 4 objetivos no son una optimización opcional,
son parte del MVP.

---

## 3. Cobertura por objetivo (tarea 7)

Medido contra el TAP de IRSA en la **posición propagada** de cada objetivo, no en
la de catálogo. El dato completo, con la lista de fechas, está en
[`config/coverage.yaml`](../config/coverage.yaml), que se regenera con
`python core/fetch_coverage.py`.

| Objetivo | Obs. | Fechas | Rango | Detectores | Obs./fecha |
|---|---|---|---|---|---|
| **Epsilon Indi B** | 445 | 60 | 2025-04-24 → 2026-10-02 | 6/6 | 7.4 |
| **WISE 0855-0714** | 256 | 27 | 2025-05-05 → 2026-05-14 | 6/6 | 9.5 |
| **RW Aurigae A** | 333 | 35 | 2025-09-01 → 2026-09-16 | 6/6 | 9.5 |
| **R Draconis** | 2483 | 222 | 2025-04-24 → 2026-09-27 | 6/6 | 11.2 |

Los cuatro tienen **cobertura de los 6 detectores**, así que los cuatro pueden
dar espectro completo de 0.75 a 5.0 µm. El número de observaciones cuenta
*planes* distintos, no filas de la consulta: un plane puede traer varios
artifacts, y contar filas infla el total.

### 3.1 R Draconis es el mejor caso de demo, por lejos

**2483 observaciones en 222 fechas distintas.** Diez veces más que cualquier otro.

La razón es su posición: R Dra está en RA 248.17°, Dec +66.75°, y el **polo
eclíptico norte** está en RA ~270°, Dec +66.56°. Cae dentro de la zona de campo
profundo de SPHEREx, que se observa muchísimo más que el cielo general.

Y además es una **Mira**, con un período de ~245 días: en 522 días de cobertura
entran dos ciclos completos de brillo. Para el objetivo O3 (ver el cambio en el
tiempo) y para el panel de espectros, es el objetivo que mejor va a lucir.

> **Recomendación para el equipo:** armar la demo principal con **R Draconis**, no
> con WISE 0855. WISE 0855 es el caso difícil y hay que resolverlo, pero no es el
> que mejor muestra la herramienta.

Una rareza que conviene revisar: en R Dra los detectores no están parejos. D1,
D3, D4 y D6 tienen 565–584 observaciones, pero **D2 y D5 solo 89**. En los otros
tres objetivos el reparto es equilibrado. Probablemente R Dra cae en el borde de
la huella del campo profundo para esos dos detectores.

### 3.2 El movimiento propio apenas se ve DENTRO de los datos de SPHEREx

Esto corrige una impresión que es fácil sacar de la sección 1, y es la conclusión
más importante de la tarea 7.

Los 21.4 píxeles de WISE 0855 son la distancia entre las **coordenadas de 2010
del enunciado** y su posición hoy. No es lo que se mueve el objeto *mientras*
SPHEREx lo observa:

| Objetivo | Ventana de datos | Días | Movimiento en la ventana |
|---|---|---|---|
| WISE 0855 | 2025-05-05 → 2026-05-14 | 374 | 8.35″ = **1.35 px** |
| eps Ind B | 2025-04-24 → 2026-10-02 | 526 | 6.75″ = **1.09 px** |
| RW Aur A | 2025-09-01 → 2026-09-16 | 380 | 0.03″ = 0.00 px |
| R Dra | 2025-04-24 → 2026-09-27 | 521 | 0.03″ = 0.00 px |

**Un video de WISE 0855 va a parecer casi estático.** Se desplaza poco más de un
píxel entre el primer y el último cuadro. Eso no invalida el objetivo O4 ("hacer
visible el movimiento"), pero sí descarta la idea de que el movimiento se vea
solo reproduciendo los cuadros.

Lo que sí puede funcionar, en orden de dificultad:

1. **Resta de imágenes** (tarea 22, consideración C5). Un desplazamiento de 1.35 px deja un residuo en forma de dipolo. Es débil pero medible, y es exactamente la técnica para la que sirve restar.
2. **Centroide con precisión sub-píxel**, graficando posición contra tiempo. Una recta limpia sobre 1.35 px es un resultado convincente, aunque no sea un video espectacular.
3. **Comparar con la posición de 2010** del propio enunciado. Ahí sí hay 21 píxeles de diferencia, pero es dato externo, no SPHEREx.

La conclusión práctica: la demo de movimiento propio necesita la resta, no solo
el reproductor. Conviene decirlo en el pitch como una decisión informada.

### 3.3 Cuántas épocas hay por banda

Esta era la pregunta abierta: con 17 canales espectrales por detector
(6 × 17 = las 102 bandas), ¿alcanza para un video de una sola banda?

| Detector | λ (µm) | R | eps Ind B | WISE 0855 | RW Aur | R Dra |
|---|---|---|---|---|---|---|
| D1 | 0.75–1.12 | 39.1 | 2.5 | 2.1 | 3.3 | **34.4** |
| D2 | 1.10–1.65 | 41.4 | 5.4 | 2.8 | 3.2 | 5.2 |
| D3 | 1.63–2.43 | 40.6 | 5.6 | 2.6 | 3.3 | **33.8** |
| D4 | 2.40–3.85 | 34.9 | 2.5 | 2.1 | 3.3 | **34.2** |
| D5 | 3.81–4.43 | 111.6 | 4.7 | 2.8 | 3.3 | 5.2 |
| D6 | 4.41–5.01 | 127.8 | 5.4 | 2.5 | 3.2 | **33.2** |

Observaciones **estimadas por banda**, repartiendo las del detector en partes
iguales entre sus 17 canales.

> **Esto es una estimación, no una medición.** En la realidad depende de dónde cae
> el objetivo en el detector cada vez, y eso no es uniforme. El número exacto por
> banda sale de leer `WCS-WAVE` de cada recorte, que es parte de la tarea 23.

Con eso, la respuesta a la pregunta es: **depende del objetivo.**

- Para **WISE 0855, eps Ind B y RW Aur**, hay 2 a 6 épocas por banda. Un video de una sola banda tiene **2 a 6 cuadros**: demasiado corto. Para llegar a las 27–60 fechas hay que mezclar bandas, y entonces el reproductor tiene que mostrar qué banda está viendo en cada cuadro, y las restas solo pueden hacerse entre cuadros comparables.
- Para **R Dra**, hay ~34 épocas por banda en D1, D3, D4 y D6. Ahí **sí** se puede hacer un video de una sola banda, con el color fijo y sin trucos.

Eso refuerza lo de 3.1: R Dra es el objetivo que permite la demo limpia.

### 3.4 Los 6 detectores no se solapan: se encadenan

Otro pendiente del README que estos datos cierran. Los rangos de longitud de onda
de los 6 detectores son **contiguos**, no superpuestos:

```
D1  0.75 ──── 1.12
D2         1.10 ──── 1.65
D3                1.63 ──── 2.43
D4                       2.40 ──── 3.85
D5                              3.81 ── 4.43
D6                                   4.41 ── 5.01
```

Los solapes son de ~0.02–0.04 µm, solo en las costuras. Entre los seis cubren
0.75 a 5.01 µm sin huecos.

**Implicación para la consideración C8** ("combinar los datos de los 6 detectores
para mejorar la señal/ruido"): no se puede entender como apilar los 6 detectores
sobre la misma banda, porque cada uno mide longitudes de onda distintas. La
mejora de señal/ruido tiene que venir de **combinar visitas repetidas a la misma
banda**. Lo que aportan los 6 detectores es *extender* el espectro, no
profundizarlo.

### 3.5 La resolución espectral da un salto en D5

`energy_resolvingpower` no es parejo: **R ≈ 35–41 en D1 a D4, pero R ≈ 112 en D5
y R ≈ 128 en D6.** El extremo rojo tiene unas tres veces más resolución
espectral.

Para el panel de espectros eso significa que **las bandas no tienen el mismo
ancho**: las de D5 y D6 son mucho más angostas. Graficar los 102 puntos como si
fueran equivalentes da una impresión equivocada de la forma del espectro. Conviene
dibujar el ancho de banda de cada punto, o al menos marcar dónde está la costura.

## 4. Bits de FLAGS (tarea 8)

El dato vive en [`config/flags.yaml`](../config/flags.yaml), transcrito a mano
de la **Tabla 16** del Explanatory Supplement (`SSDC-DP-017` v2.0, 2026-08-25,
páginas 31–33). Se decodifica con [`core/flags.py`](../core/flags.py).

### 4.1 El bit 21 era la máscara de fuentes

La Fase 0 vio que **un bit aparece en ~41 % de los píxeles** y lo dejó como
incógnita. Es el bit 21, **`SOURCE`: "píxel mapeado a una fuente conocida"**.

No es un defecto. Es la máscara de fuentes del pipeline, y es exactamente la
**"máscara de contaminación"** que pide la consideración C6 del enunciado. Que
cubra el 41 % de un recorte es lo esperable en un campo poblado.

### 4.2 No existe "la máscara de píxeles malos"

Esto es lo más importante de la tarea 8. El documento da **dos listas distintas**
de enmascarado (páginas 42–43), y la diferencia decide si la fotometría sirve:

| | Fondo | Fotometría |
|---|---|---|
| Para qué | estimar el cielo alrededor de la fuente | medir el flujo de la fuente |
| Nº de flags | 15 | 11 |
| `SOURCE` | **se enmascara** | **NO se enmascara** |
| `TRANSIENT` | se enmascara | no |
| `OVERFLOW` | se enmascara | no |
| `OUTLIER` | se enmascara | no |

La lista de fotometría es un subconjunto estricto de la del fondo. Los cuatro
flags que las diferencian son `SOURCE`, `TRANSIENT`, `OVERFLOW` y `OUTLIER`.

**El error que esto evita:** enmascarar "todos los píxeles marcados" antes de
hacer fotometría borra el objetivo, porque `SOURCE` marca precisamente los
píxeles de la fuente que se quiere medir. Y como cubre el 41 % del recorte, el
resultado no es un error ruidoso: es un espectro de cielo vacío que parece
plausible. Por eso `core.flags.mask_for()` **exige** que se diga el propósito;
no tiene valor por defecto.

La prueba `test_photometry_mask_keeps_the_target_pixel` en
[`core/test_flags.py`](../core/test_flags.py) fija esa distinción de punta a
punta, para que nadie la "simplifique" más adelante.

### 4.3 Qué quedó sin resolver en la propia fuente

- **9 bits no aparecen en la Tabla 16**: 3, 4, 5, 8, 13, 16, 18, 30 y 31. No se
  les inventó significado: están en `unassigned_bits`. Si alguno aparece activo
  en datos reales, el documento que tenemos quedó viejo, y
  `core.flags.undocumented_bits_present()` lo detecta en vez de ignorarlo.
- **`FULLSAMPLE` (bit 12) es ambiguo.** El documento dice *"Not usable for
  science, purely informational"*. La lectura razonable es que **el flag** es
  informativo (marca los píxeles de la región rotatoria de lectura completa de
  8×32), no que el píxel esté dañado. Lo respalda que no figura en ninguna de
  las dos listas de enmascarado. Si se enmascarara, se tiraría dato bueno.
- **`GHOST_FPA` (bit 23) está obsoleto**: absorbido en `GHOST_EXT`, y el
  documento dice que se elimina en el procesamiento del año 2. Marcado como
  `deprecated` en el YAML.
- **`FINAST`** aparece como "Fine Astrometry flag" entre las salidas del módulo
  de astrometría, pero **no está en la Tabla 16**. No confirmado como bit por
  píxel; queda anotado en `otros_bitmasks`.

### 4.5 El header del FITS es una segunda fuente, y no dice lo mismo

Camilo avisó que los significados de los bits vienen en el FITS. **Es cierto**:
el header de la extensión `FLAGS` trae tarjetas `MP_<NOMBRE> = <bit>`, y ahí
está `MP_SOURCE = 21 / Pixel mapped to a known source`. Lo verifiqué contra un
cutout real (release `l2b-v20-2025-251`).

Pero las dos fuentes **no son equivalentes**, y la diferencia va en las dos
direcciones:

| | Tabla 16 del documento | Header FITS |
|---|---|---|
| Bits que define | 23 | 16 |
| `PHANTOM` (4), `REFERENCE` (5) | **no los tiene** | sí |
| `CROSSTALK` (20), los `GHOST`, `STREAK`, `BLOOM`, `SNOWBALL`, `HALO`, `SATELLITE_HALO` (22–29) | sí | **no los tiene** |
| Las dos listas de enmascarado | **sí** | no |
| Viaja con los datos | no | **sí** |

Los 14 bits que aparecen en las dos coinciden en número y significado, lo que
valida la transcripción. Y los 2 que solo trae el header, `PHANTOM` y
`REFERENCE`, **estaban en mi lista de bits sin documentar**: ahora están en
`flags.yaml` marcados con `origin: fits_header`.

Así que ninguna fuente alcanza sola. Lo que sí cambia, y es una mejora real, es
que el header **viaja con los datos**: si un release futuro mueve o agrega bits,
el FITS lo dice y el PDF puede tardar meses. Para eso está
`core.flags.cross_check_fits(header)`, que compara un header real contra
`flags.yaml` y reporta desajustes, bits nuevos y bits que solo conoce el
documento. Corrido contra el cutout real: **16 bits coinciden, cero desajustes,
cero bits nuevos.** Es la pieza que faltaba para la consideración C1.

Quedan **7 bits** sin definir en ninguna de las dos fuentes: 3, 8, 13, 16, 18,
30 y 31.

### 4.6 La trampa confirmada con datos reales

El recorte de R Dra que bajé para verificar todo esto dio la demostración
perfecta de por qué importa elegir bien la máscara. Es un recorte de 29×29 =
841 píxeles, y **el 100 % tiene el flag `SOURCE`**: cae entero dentro de una
máscara de fuentes, porque R Dra es una estrella brillante en un campo poblado.

| Máscara | Píxeles usables | Resultado |
|---|---|---|
| `photometry` | 790 / 841 (93.9 %) | flujo medible |
| `background` | **0 / 841** | nada |
| "todo lo marcado" | **0 / 841** | fotometría imposible |

O sea: no es que usar la máscara equivocada dé un número un poco peor. Da
**cero píxeles**.

De paso, un hallazgo para la tarea 23: en campos poblados **puede no haber fondo
local limpio dentro del recorte**. Si el 100 % de los píxeles es `SOURCE`, no hay
anillo de cielo que medir, y el fondo hay que estimarlo de una apertura más
grande o del modelo `ZODI`.

### 4.7 Las cuentas del header son de la imagen completa

El header también trae tarjetas `L2 N_<NOMBRE>` con los píxeles marcados de cada
flag, ya contados por el pipeline. Tentador, pero **son de la imagen de
2040×2040, no del recorte**: en el cutout de 29×29 el header dice
`L2 N_OUTLIER = 98707`, más que los 841 píxeles que tiene el recorte entero.

Si el panel de metadata muestra esos números como si fueran del recorte, miente
por varios órdenes de magnitud. Para el recorte hay que contar sobre el array,
con `core.flags.bit_counts()`. Está anotado en `api.md` y en `flags.yaml`.

### 4.4 Para el frontend y el backend

`core.flags.bit_counts(capa)` devuelve, ordenado de más a menos frecuente, cuántos
píxeles tiene cada flag y qué fracción del recorte representan — listo para el
panel de metadata y la capa de máscaras (C6, tareas 19 y 20).

```python
import core.flags as f
f.decode(valor)                     # ['SOURCE', 'HOT']
f.mask_for(capa, "photometry")      # True donde hay que EXCLUIR
f.good_pixels(capa, "background")   # el complemento
f.bit_counts(capa)                  # para el panel de metadata
```

Hay un bitmask aparte, `CONTAINS_BAD_PIXEL` (bit 32), que **no** es de la capa
`FLAGS` por píxel: es de la fotometría de Level 3. El documento aclara que es un
aviso conservador y que no implica descartar la medición.

---

## 5. Cómo reproducir todo esto

```bash
pip install numpy astropy pyyaml certifi
python core/fetch_targets.py      # regenera config/targets.yaml desde SIMBAD
python core/targets.py            # tabla resumen de los objetivos
python core/flags.py              # tabla de bits de FLAGS y las dos máscaras
python core/fetch_coverage.py     # regenera config/coverage.yaml desde IRSA
python core/test_targets.py       # 10 pruebas, incluida la de la época
python core/test_flags.py         # 26 pruebas de bits y máscaras
```
