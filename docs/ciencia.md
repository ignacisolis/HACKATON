# Notas de ciencia · rol C

Lo que el resto del equipo necesita saber del lado científico, y de dónde sale
cada número. Mantiene esta página el rol C (Nacho).

Estado: **tareas 5, 6, 7, 8, 21 y 22 cerradas.** Toda la Fase 0 del rol C está
lista, más la Fase 2 completa. Queda la 23 (espectros) y la 27 (validar).

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

## 5. Alineación (tarea 21)

`core.align_frames()` recentra una serie de recortes sobre el objetivo, de modo
que quede en el mismo píxel en todos los cuadros. Es la condición para hacer un
video, restar imágenes o sumar apertura.

Resuelve **dos cosas distintas** a la vez, y conviene no confundirlas: que el
objetivo se mueve en el cielo (movimiento propio, lo da `targets.py`) y que cada
exposición apunta distinto (lo da el WCS de cada recorte).

### 5.1 Tres decisiones, y por qué

**Los `FLAGS` se remuestrean por vecino más cercano, nunca bilineal.** Interpolar
un bitmap mezcla bits de píxeles vecinos e inventa combinaciones que nunca
existieron: el promedio de `SOURCE` (2²¹) y nada no es "medio SOURCE", es basura.

**La varianza se propaga con los pesos al cuadrado.** Si un píxel de salida es
Σ wᵢ·vᵢ, su varianza es Σ wᵢ²·varᵢ. Por eso el remuestreo está escrito a mano en
vez de usar `scipy.ndimage`: así la varianza usa exactamente los mismos pesos
que la imagen.

> Ojo con leer la varianza de más: al interpolar **baja** (cuatro pesos de 0.25
> dan un cuarto de la varianza original), pero eso **no** es mejor señal/ruido.
> El ruido queda correlacionado entre píxeles vecinos. La ganancia real viene de
> combinar visitas repetidas, que es `coadd()` en la tarea 22.

**Los píxeles sin dato se marcan con `MISSING_DATA`**, además de quedar `NaN` en
la imagen. Es la opción más segura: ese bit está en las **dos** listas de
enmascarado del documento, así que `core.flags.mask_for()` los excluye sin que
nadie tenga que acordarse de hacerlo. **Esto le importa al backend:** los NaN del
cubo no son un error, son borde de remuestreo, y ya vienen marcados.

### 5.2 Qué se probó

El criterio de aceptación del Tablero ("WISE 0855 queda centrado en cada fecha")
es una prueba literal: construye cuadros en la posición **real** del objeto en 5
fechas distintas, con apuntados distintos, y verifica que tras alinear el
centroide queda a menos de 0.1 px del centro en todos.

Y hay una contraprueba que es la que le da sentido: alinear contra las
coordenadas J2000 **sin** propagar deja la fuente fuera del recorte. Sin eso,
centrar podría estar funcionando por casualidad.

También se verificó contra el **recorte real** de R Dra, con su WCS `TAN-SIP` y
distorsión incluida: el objetivo se ubica en (14.14, 14.35) de 29×29 y el
corrimiento aplicado es exacto.

### 5.3 Una limitación medida, no supuesta

`centroid()` es un centroide ponderado por flujo, sin restar fondo ni rechazar
vecinos. Sobre una fuente aislada da mejor que 0.1 px; sobre el recorte real de
R Dra **se desvía 0.7 px**, porque es un campo poblado con fondo alto y el
estimador se sesga con las fuentes de al lado.

No es un fallo de la alineación: el corrimiento aplicado fue exacto. Pero
significa que para medir el movimiento propio de WISE 0855 en serio —que son
1.35 px en toda la ventana— hace falta restar fondo y ajustar una PSF. Eso es
parte de la tarea 23, y conviene no prometer precisión sub-píxel antes.

## 6. Resta y apilado (tarea 22)

`core.subtract_frames()` y `core.subtract_aligned()` restan dos cuadros
comparables; `core.coadd()` apila visitas repetidas; `core.dipole_snr()` mide el
dipolo que deja un objeto en movimiento.

### 6.1 Hay dos formas de alinear y eligen qué se ve

No son dos maneras de hacer lo mismo:

| Alineado sobre | Qué queda fijo | Para qué sirve |
|---|---|---|
| el **objetivo** (`target_key=...`) | el objetivo | apilar, fotometría, espectros |
| el **cielo** (`ra=`, `dec=`) | el fondo | **restar** y ver movimiento propio |

Si se resta un cubo alineado sobre el objetivo, el objetivo se cancela y el
movimiento **no se ve**: la resta queda vacía, que parece un resultado correcto.
Es el mismo patrón de fallo silencioso que las coordenadas de 2010 y la máscara
`SOURCE`. Por eso el cubo lleva `aligned_on` y `subtract_aligned()` se niega,
explicando qué hacer, salvo que se pase `warn_if_target_aligned=False`.

### 6.2 El hallazgo con datos reales: casi nada es comparable

Bajé **6 recortes reales** de R Dra del detector D2 y medí la longitud de onda
en la posición del objetivo, de `WCS-WAVE`:

| # | MJD | λ (µm) | ancho (µm) |
|---|---|---|---|
| 0 | 60834.7884 | 1.4017 | 0.0336 |
| 1 | 60834.7899 | 1.4359 | 0.0347 |
| 2 | 60834.7914 | 1.4706 | 0.0357 |
| 3 | 60834.7929 | 1.5067 | 0.0368 |
| 4 | 60835.5358 | 1.5431 | 0.0376 |
| 5 | 60835.5373 | 1.5806 | 0.0383 |

**0 de 15 pares resultaron comparables.**

Y la razón es estructural, no un problema de la tolerancia: cada exposición
consecutiva se corre ~0.035 µm, que es **casi exactamente un ancho de banda**.
SPHEREx va cambiando de canal espectral entre exposiciones; así construye las
102 bandas. O sea: **seis exposiciones seguidas dan seis bandas distintas, no
seis medidas de una banda.**

De paso, esto **confirma empíricamente los 17 canales por detector**, que hasta
ahora venían de las notas de Fase 0: D2 cubre 1.10–1.65 µm = 0.55 µm, y
0.55 / 0.035 ≈ 16.

**Lo que implica para la consideración C5 y para el backend:** los pares
comparables hay que buscarlos **en todo el archivo**, no entre exposiciones
vecinas. De las 89 observaciones de D2 sobre R Dra, las que caen en el mismo
canal son ~5 (sección 3.3). Conviene que `/api/frames` exponga el **canal** de
cada cuadro, no solo el detector y la λ, para que el frontend pueda ofrecer
pares válidos en vez de dejar que el usuario elija dos cualesquiera y reciba un
error.

### 6.3 Qué cuenta como "se movió", medido

`dipole_snr()` pide tres cosas, y la tercera salió de medirla:

1. Los **dos** lóbulos sobre el umbral. Un pico positivo solo puede ser un rayo
   cósmico o un cambio de brillo.
2. Separación mayor que cero.
3. Los dos lóbulos **juntos**, a menos de 4 px.

El punto 3 no es un número elegido a dedo. Con el desplazamiento real de WISE
0855 los lóbulos quedan a **2.0 px**; en un par **sin** movimiento aparecían dos
picos de 3.5 y 6.2 sigma pero a **8.1 px**, en esquinas opuestas de la caja. Sin
el límite de separación, eso pasaba por detección. Una fuente puntual desplazada
deja el positivo y el negativo pegados; dos picos lejanos son dos cosas
distintas.

### 6.4 Limitación: no se igualan las PSF

La resta es directa. Si los dos cuadros se remuestrearon con corrimientos
distintos, uno queda más suavizado que el otro y la diferencia deja residuos
alrededor de **todas** las fuentes del campo. Medido en el par sin movimiento:
hasta **6 sigma**.

Por eso `detected` significa "hay algo con forma de dipolo acá", no "este objeto
se movió con certeza". Para una medición publicable hay que convolucionar los dos
cuadros a una PSF común, y para eso está la extensión `PSF` de los FITS — la
misma que la caché descarta por peso, así que habría que traerla aparte. Queda
para la tarea 27.

La prueba `test_la_resta_sin_igualar_psf_deja_residuos` fija esa limitación: si
algún día falla, es buena noticia, y entonces se puede endurecer `dipole_snr`.

### 6.5 Un sesgo en la longitud de onda que conviene saber

`WCS-WAVE` trae los coeficientes SIP espaciales pero su `CTYPE` es `WAVE-TAB`,
y astropy avisa que **aplica el SIP igual**. Medí cuánto cambia: **0.003 µm**,
un 9 % del ancho de banda.

No alcanza para cambiar si dos cuadros son comparables (el umbral son 0.017 µm),
así que la tarea 22 no se ve afectada. Pero son 3 nm de sesgo sistemático cuando
IRSA documenta `WCS-WAVE` como una aproximación de ~1 nm. Para el visor alcanza;
para un número publicable hay que usar el producto **Spectral WCS** (`CWAVE` y
`CBAND`), como recomienda IRSA. Importa para la tarea 23.

## 7. Cómo reproducir todo esto

```bash
pip install -r requirements.txt
python core/fetch_targets.py      # regenera config/targets.yaml desde SIMBAD
python core/targets.py            # tabla resumen de los objetivos
python core/flags.py              # tabla de bits de FLAGS y las dos máscaras
python core/fetch_coverage.py     # regenera config/coverage.yaml desde IRSA
python core/test_targets.py       # 10 pruebas, incluida la de la época
python core/test_flags.py         # 35 pruebas de bits y máscaras
python core/test_align.py         # 26 pruebas de alineación
python core/test_subtract.py      # 25 pruebas de resta y apilado
```
