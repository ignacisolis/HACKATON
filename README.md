# Visor web de SPHEREx: el cielo en el tiempo

> Proyecto para el **Hackathon NASA · SPHEREx**. Nombre del proyecto: **HackatonNASA**.
> Estado: **Fase 1 (MVP) en curso.** Fecha límite del hackathon: **15 de noviembre de 2026**.
> Stack: Python + FastAPI (backend y ciencia) · frontend web (por confirmar por B).

---

## 1. Contexto

**SPHEREx** es un telescopio espacial de la NASA que mapea el cielo completo en el infrarrojo cercano, **una vez cada 6 meses**, en **102 bandas** de color (de ~0.75 a ~5 µm). Esas bandas son sensibles a la huella de varias moléculas, como hidrógeno, agua y dióxido de carbono, entre otras.

Cada exposición se toma con **6 detectores** (D1 a D6), y cada uno cubre un rango distinto de longitudes de onda. Los datos son públicos y se alojan en el archivo **IRSA (NASA/IPAC)**.

## 2. El problema

Hay imágenes de **más de mil millones de objetos**: enanas cafés, quásares, cometas, asteroides, estrellas, supernovas y galaxias. Estos objetos:

- se **superponen** entre sí en las imágenes, y
- **cambian de brillo** con el tiempo.

Para la comunidad hacen falta herramientas nuevas que permitan ver y analizar esos cambios de forma sencilla.

## 3. Meta del proyecto

> Crear una **web pública** que muestre imágenes del cielo de SPHEREx de forma fácil de ver, y que permita **ver cómo cambian a lo largo del tiempo**.

El usuario ingresa las **coordenadas** (ascensión recta y declinación) de una parte del cielo, y la herramienta entrega **una serie de imágenes de ese segmento, reproducida como video o series de tiempo**, de modo que sea fácil notar el movimiento de los objetos.

## 4. Objetivos

### 4.1 Objetivos principales (requisitos del enunciado)

| # | Objetivo | Cómo sabremos que está listo |
|---|---|---|
| O1 | Web pública y accesible | Hay un link que cualquiera puede abrir sin instalar nada |
| O2 | Entrada por coordenadas (RA y Dec) | El usuario escribe coordenadas (grados y/o hh:mm:ss) y ve su zona del cielo |
| O3 | Serie de imágenes como **video** en el tiempo | Reproductor con play/pausa, velocidad y control de tiempo |
| O4 | Hacer visible el movimiento de objetos | Un objeto con movimiento propio se ve desplazarse con claridad |
| O5 | Probar la herramienta con 4 casos | Los 4 objetos de prueba (abajo) funcionan con link de demo |

### 4.2 Casos de prueba obligatorios

| Objeto | Qué es | Qué demostrar |
|---|---|---|
| **Epsilon Indi B** | Un par de enanas cafés que orbitan una estrella | Se ve la zona del sistema (ver nota sobre resolución en la sección 7) |
| **WISE 0855** (08h55m10.831s, −07°14′42.53″) | Objeto muy frío y débil, con movimiento propio muy alto | Su desplazamiento en el tiempo |
| **RW Aurigae** | Estrella variable | Cambio de brillo en el tiempo |
| **R Draconis** | Estrella variable evolucionada | Cambio de brillo. **Saturado:** no admite fotometría, ver `docs/ciencia.md` 8.2 |

### 4.3 Consideraciones especiales (del enunciado)

| # | Consideración | Prioridad |
|---|---|---|
| C1 | **Fácil de actualizar** cuando salgan las versiones finales de los datos de SPHEREx | Imprescindible |
| C2 | Entregar las **102 bandas** de forma fácil y rápida | Imprescindible |
| C3 | Que el usuario **elija la banda** con la que quiere trabajar | Imprescindible |
| C4 | **Coordenadas en la URL**, para compartir exactamente la misma vista | Imprescindible |
| C5 | **Sumar y restar imágenes** para identificar objetos en movimiento | Muy valioso |
| C6 | Mostrar la **metadata** de las imágenes, incluidas las **máscaras de contaminación** | Muy valioso |
| C7 | **Mostrar espectros al instante** (punto extra) | Muy valioso |
| C8 | **Combinar los datos de los 6 detectores** para mejorar la relación señal/ruido | Extra |
| C9 | Inspirarse en sitios públicos de astrofísica como **Aladin** | Extra |

### 4.4 Ideas propias que surgieron (opcionales)

- **Panel de tabla tipo TOPCAT:** tabla ordenable y filtrable de las observaciones que cubren el punto (fecha, detector, longitud de onda, versión).
- **Agente de IA dentro de la web**, limitado a manejar la interfaz gráfica (ir a coordenadas, elegir banda, restar imágenes, etc.). Solo después de que lo esencial funcione.
- **Cross match con otras misiones espaciales**, Podría ser buena idea y practica hacer crossmatch con distintas misiones espaciales para la extracción de características fotométricas.  

### 4.5 ¿Qué significa "coordenadas en la URL"?

La dirección web guarda lo que el usuario está viendo. Por ejemplo:

```
https://tuapp.org/?ra=133.795&dec=-7.245&band=45&fov=0.1
```

Quien reciba ese link ve exactamente el mismo punto del cielo, la misma banda y el mismo zoom. Sirve para compartir hallazgos y para que otras páginas (como Aladin) abran nuestro visor.

---

## 5. Lo aprendido en la Fase 0

> Lo marcado con _(por verificar)_ es inferencia o conocimiento general, no un dato confirmado con los datos del proyecto.

### Estructura de los datos
- Los archivos principales son **Spectral Images en formato MEF** (FITS con varias extensiones), de ~70 MB cada uno, uno por exposición y detector.
- Extensiones: `IMAGE` (MJy/sr), `FLAGS` (bitmap de calidad), `VARIANCE`, `ZODI` (modelo de luz zodiacal, **no restado**), `PSF` y `WCS-WAVE`.
- Un **cutout** (recorte) devuelve las mismas extensiones pero recortadas. La `PSF` se entrega **sin recortar** (121×101×101 float32 ≈ 4.9 MB), así que ocupa ~99 % del peso de un cutout de 59×59 píxeles.
- Un píxel de SPHEREx mide ~6.2″. Un recorte de 0.1° tiene ~59×59 píxeles.

### Longitud de onda
- **Cada píxel tiene su propia longitud de onda.** Una exposición no es una banda: el objetivo cae en una longitud de onda concreta en cada exposición. En un recorte pequeño la longitud de onda casi no cambia (por ejemplo, 1.507 a 1.526 µm).
- Para armar las 102 bandas hay que **juntar exposiciones distintas**.
- Cada detector cubre un rango distinto (en nuestros datos: D1 ~1.0 µm, D2 ~1.5, D3 ~2.4, D4 ~3.4, D5 ~4.3, D6 ~5.0). Los 6 detectores **extienden** el espectro; la mejora de señal/ruido viene de combinar mediciones repetidas de la misma banda. Falta confirmar si algún rango se solapa _(por verificar)_.
- `WCS-WAVE` es una aproximación para visualización (~1 nm). Para ciencia, IRSA recomienda el producto aparte **Spectral WCS** (`CWAVE` y `CBAND`, ~32 MB por detector).

### Cobertura de WISE 0855
- **256 observaciones** en **27 fechas distintas**, entre 2025-05-05 y 2026-05-14, con los 6 detectores (36 a 48 observaciones por detector).
- Cada detector tiene 17 canales espectrales, así que hay solo **2 o 3 observaciones por banda** _(inferencia a partir de los números anteriores)_. Un video de una sola banda sería muy corto; para llegar a 27 fechas hay que mezclar bandas, y entonces las restas deben hacerse solo entre exposiciones comparables.

### Comparar imágenes
- El flujo en el objetivo varía de ~0.15 a ~0.8 MJy/sr según el detector, y sigue la forma de un fondo. **No se pueden restar imágenes de distinta longitud de onda.** Regla: restar solo exposiciones del mismo detector y con longitud de onda parecida, tras alinearlas con el WCS.

### Movimiento propio (muy importante) — ✅ verificado

> Medido contra SIMBAD en la tarea 6. Los valores de abajo ya no son inferencia.
> Detalle y fuentes en [`docs/ciencia.md`](docs/ciencia.md) y
> [`config/targets.yaml`](config/targets.yaml).

- Las coordenadas de WISE 0855 del enunciado son de la **época de descubrimiento WISE (~2010.5)**, codificadas en su designación. Su movimiento propio es de **8.15″/año**, así que al final de la ventana de SPHEREx el objeto está a **132.9″ = 21.4 píxeles** de esa posición.
- eps Ind B se mueve a **4.68″/año**: **20.2 píxeles** de deriva entre J2000 y 2026.
- **RW Aur y R Dra no necesitan corrección**: 0.0275″/año y 0.0215″/año, o sea menos de un cuarto de píxel en 26 años.
- Las coordenadas de catálogo están a época **J2000.0**, confirmado con una prueba: propagar WISE 0855 de J2000 a 2010.5 reproduce su designación con **0.41″** de diferencia, cuando un año de error de época daría 8.15″.
- Apuntar a las coordenadas del enunciado **no produce un error visible**: devuelve un recorte de cielo que parece normal, lleno de otras fuentes, sin el objetivo.
- **Pero dentro de los datos de SPHEREx el movimiento es chico:** WISE 0855 se desplaza solo **1.35 px** entre su primera y su última observación, y eps Ind B **1.09 px**. Un video no alcanza para mostrarlo; hace falta la resta de imágenes. Ver [`docs/ciencia.md`](docs/ciencia.md) sección 3.2.

### Resolución de eps Ind B
- La separación entre las dos enanas cafés es de ~0.72″, muy menor al píxel de ~6.2″: **aparecerán mezcladas como un solo objeto**. No se promete verlas como dos puntos.

### Velocidad
- La consulta TAP a IRSA tardó ~8.6 s para WISE 0855. Los cutouts y la resolución de nombres (Sesame) fueron lo más lento, y Sesame falló con timeouts desde nuestra red.
- Una consulta de varios segundos es demasiado lenta para una web interactiva: hay que **cachear y precalcular**.

### FLAGS — ✅ resuelto

> Los 23 bits documentados están transcritos en
> [`config/flags.yaml`](config/flags.yaml), del Explanatory Supplement
> SSDC-DP-017 v2.0 (Tabla 16).

- **El bit 21 que dominaba (~41 % de los píxeles) es `SOURCE`: "píxel mapeado a una fuente conocida".** No es un defecto, es la máscara de fuentes. Es justamente la "máscara de contaminación" que pide la consideración C6.
- **No existe "la máscara de píxeles malos".** El documento da **dos listas distintas**: para estimar el **fondo** se enmascara `SOURCE`, `TRANSIENT`, `OVERFLOW` y `OUTLIER`; para **fotometría** esos cuatro **no** se enmascaran. Enmascarar `SOURCE` al medir una fuente borra el objetivo.
- Hay **9 bits sin significado documentado** (3, 4, 5, 8, 13, 16, 18, 30, 31). Siguen sin asumirse: si alguno aparece activo en datos reales, es señal de que el documento quedó viejo, y `core.flags.undocumented_bits_present()` lo detecta.
- `FULLSAMPLE` (bit 12) no se enmascara: es informativo, no un defecto. Enmascararlo tiraría dato bueno.

---

## 6. Arquitectura propuesta

```
Usuario ──► Frontend (visor, video, espectro, URL) ──► Backend (API) ──► IRSA (TAP + cutouts)
                                                           │
                                                           └──► Caché compacta (sin PSF) + funciones de ciencia (core/)
```

- **Datos:** TAP de IRSA (`https://irsa.ipac.caltech.edu/TAP`, tablas `spherex.plane` y `spherex.artifact`). A cada URL se le añade `?center=RA,Dec&size=...` para obtener el cutout.
- **Caché compacta:** guardar solo `IMAGE`, `VARIANCE`, `FLAGS`, `ZODI`, WCS y mapa de longitud de onda (~100 KB por exposición en vez de ~5 MB). Precalcular los 4 objetivos de la demo.
- **Carga progresiva:** descargar en paralelo (máx. ~10 hilos) y mostrar cuadros a medida que llegan.
- **Configuración separada del código** (YAML/JSON): URL de datos, versión del release y mapeo de bandas, de modo que pasar a la versión final sea editar un archivo (C1). Los releases viajan en la ruta del archivo (por ejemplo `l2b-v20-2025-241`) y puede haber varios a la vez.
- **API propuesta** (sujeta a acuerdo del equipo):
  - `GET /api/frames?ra=&dec=&size=&band=` → cuadros con fecha, detector, longitud de onda y URL de imagen
  - `GET /api/spectrum?ra=&dec=` → pares longitud de onda / flujo
  - `GET /api/frame/{id}/meta` → metadata y bits de `FLAGS`

---

## 7. Roadmap por fases

| Fase | Contenido | Entregable |
|---|---|---|
| **0. Preparación** (sem. 1) | Entender los FITS, la API de IRSA y los visores existentes | Notebook que, dadas coordenadas, baja y explora un cutout |
| **1. MVP** (sem. 2–3) | Formulario de coordenadas, backend que lista y recorta observaciones, reproductor de video, despliegue público | Link público funcionando para una banda |
| **2. Funciones clave** (sem. 4–6) | Selector de banda, coordenadas en URL, alineación con WCS, suma y resta de imágenes, metadata y máscaras | WISE 0855 con su movimiento claramente visible |
| **3. Espectros y señal** (sem. 6–8) | Espectro instantáneo, combinación de detectores, rapidez (cubos y caché) | Espectro de una enana café y de una variable |
| **4. Casos científicos** (sem. 8–9) | Los 4 objetos con link permanente | Demo por objeto |
| **5. Actualización y robustez** (sem. 10) | Configuración de versión, script de datos nuevos, manejo de errores, pruebas automáticas | El proyecto sobrevive a una actualización de datos |
| **6. Pulido y presentación** (sem. final) | Interfaz clara, Aladin/SIMBAD, README en inglés, video demo, pitch | Presentación final |

_Las semanas eran orientativas: con entrega el **15 de noviembre** hay ~5 días, así que se prioriza la lista "Imprescindible" de abajo y lo demás entra solo si sobra tiempo._

### Prioridades si el tiempo aprieta
1. **Imprescindible:** coordenadas → video, selector de banda, URL con coordenadas, los 4 objetos funcionando.
2. **Muy valioso:** restar/sumar imágenes, espectro instantáneo, máscaras de `FLAGS`.
3. **Extra:** combinar detectores, Aladin, cubos precalculados, panel tipo TOPCAT, agente de IA.

---

## 8. División del trabajo (3 personas)

> Reparto **confirmado** (Nacho, 2026-11-10). Falta solo volcarlo a
> `docs/EQUIPO.md`, que es la condición de cierre de la tarea 2 del Tablero.

| Rol | Responsable | Rama | Carpeta | Es dueño de |
|---|---|---|---|---|
| **A · Datos y backend** | Camilo | `back` | `backend/` | Acceso a IRSA, caché, API, configuración de versiones, script de actualización, despliegue del backend. También integración |
| **B · Frontend y experiencia** | Bruno | `front` | `frontend/` | Formulario, reproductor, selector de banda, URL, panel de espectro, capa de máscaras, Aladin, despliegue de la web |
| **C · Ciencia y procesamiento** | Nacho | `ciencias` | `core/` | Alineación, imagen de referencia, restas, espectros, combinación de detectores, validación con los 4 objetos, documentación y presentación |

Reglas de trabajo:
- Acordar la API en la primera semana, para que B trabaje con datos falsos mientras A termina el backend real.
- C entrega funciones puras de Python (reciben arrays, devuelven arrays) que A llama desde la API.
- Un solo repositorio con carpetas separadas y ramas por persona; sincronización breve 2 o 3 veces por semana.
- Cada uno trabaja **solo en su carpeta y en su rama**. Lo que cruza carpetas va en `contracts/api.md`.
- Un responsable de integración (sugerido: A).

---

## 8.1 Kit de herramientas por persona

Qué instala cada uno, con qué servicios habla y qué trampas ya están
documentadas, para no volver a tropezar con ellas.

### Kit común (los tres)

```bash
git clone https://github.com/ignacisolis/HACKATON.git
cd HACKATON
git checkout <tu rama>        # ciencias | front | back
```

| Herramienta | Para qué |
|---|---|
| **Python 3.12** | Todo el lado de datos y ciencia. En la máquina de Nacho: 3.12.10 |
| **Git + GitHub** | Una rama por persona; nadie commitea en `main` |
| **Notion** | [Tablero](https://app.notion.com/p/12b60357f1d74d24a962ce0aeafeb614) para el estado de las tareas, [Bitácora](https://app.notion.com/p/6d7bd37960934ddcafb66079012cb849) al terminar cada sesión |
| **`contracts/api.md`** | La única fuente de verdad de lo que se pasa entre carpetas |

> El **stack** de la web todavía no está decidido: es la tarea 1 del Tablero.
> Lo que sigue marcado como _propuesto_ puede cambiar en la primera sync.

---

### Camilo · A — Datos y backend — rama `back`, carpeta `backend/`

```bash
pip install numpy astropy pyyaml httpx
pip install fastapi uvicorn          # propuesto, pendiente de la tarea 1
```

| Herramienta | Para qué |
|---|---|
| **`astropy`** | Abrir los FITS MEF, leer el WCS espacial y el espectral (`key="W"`) |
| **`numpy`** | Los arrays de `IMAGE`, `VARIANCE`, `FLAGS`, `ZODI` |
| **`pyyaml`** | Leer `config/release.yaml` y `config/targets.yaml`. Es lo que hace que cambiar de release sea editar un archivo (C1) |
| **`httpx`** | Bajar cutouts en paralelo. IRSA pide no pasarse de ~10 conexiones |
| **FastAPI + uvicorn** | La API. _Propuesto_ |

**Servicios con los que habla** (es el único rol que toca IRSA):

| Servicio | URL | Estado |
|---|---|---|
| IRSA TAP | `https://irsa.ipac.caltech.edu/TAP/sync` | funciona, **~16 s** la primera consulta |
| Tablas | `spherex.plane` (polígono por observación), `spherex.artifact` | |
| Cutouts | a la URL del artifact se le agrega `?center=RA,Dec&size=...` | |

**Lo que le pide a `core/`** — antes de recortar, preguntar dónde está el objeto ESE día:

```python
import core.targets as t
ra, dec = t.target_position("wise_0855", mjd)   # MJD del header FITS
```

**Trampas ya documentadas:**
- La extensión **`PSF` viene sin recortar** (~4.9 MB) y es ~99 % del peso de un cutout de 59×59. La caché compacta la tira.
- **`ZODI` no está restado** de `IMAGE`. Es un modelo de referencia.
- Esos **16 s** de latencia confirman que la caché y el precálculo de los 4 objetivos **no son una optimización opcional**: sin eso la web no es interactiva.

---

### Bruno · B — Frontend — rama `front`, carpeta `frontend/`

| Herramienta | Para qué | Estado |
|---|---|---|
| **`contracts/fixtures/`** | Los 12 cuadros falsos. Permiten construir todo el visor **sin esperar al backend** | listo |
| Framework web | Formulario, reproductor, selector de banda | _por decidir, tarea 1_ |
| Librería de gráficos | El panel de espectro (λ vs flujo) | _por decidir_ |
| **Aladin Lite** | Abrir la misma posición en un visor de cielo estándar (C9) | extra |
| Parámetros de URL | `?ra=&dec=&band=&fov=` para que la vista sea compartible (C4) | — |

**Lo que recibe del backend:** cada cuadro trae fecha, detector y longitud de onda. El video se filtra por banda.

**Trampas ya documentadas:**
- Hay solo **2 o 3 épocas por banda**. Un video de una sola banda es cortísimo; para llegar a las 27 fechas hay que mezclar bandas, y eso hay que mostrarlo en la interfaz.
- Un píxel son **6.2″**. No prometer ver pares de estrellas separados: eps Ind Ba/Bb (0.72″) y RW Aur A/B (~1.4″) salen como un solo punto.
- La meta ya incluye **"video o series de tiempo"**, no solo video.

---

### Nacho · C — Ciencia — rama `ciencias`, carpeta `core/`

```bash
pip install numpy astropy pyyaml certifi
pip install matplotlib               # para graficar espectros
```

| Herramienta | Para qué |
|---|---|
| **`astropy`** | WCS, `SkyCoord`, propagación de movimiento propio, fotometría |
| **`numpy`** | Alineación, restas, combinación ponderada |
| **`pyyaml`** | Escribir y leer `config/targets.yaml` y `config/flags.yaml` |
| **`certifi`** | Imprescindible: sin su bundle de certificados, SIMBAD falla el TLS |

**Servicios con los que habla:**

| Servicio | URL | Estado |
|---|---|---|
| SIMBAD TAP | `https://simbad.harvard.edu/simbad/sim-tap/sync` | **funciona**, ~0.5 s |
| ~~SIMBAD Estrasburgo~~ | `simbad.u-strasbg.fr` | **no resuelve por DNS** |
| ~~SIMBAD CDS~~ | `simbad.cds.unistra.fr` | falla el TLS y su TAP da 404 |
| Explanatory Supplement | [PDF de IRSA](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp_QR.pdf) | fuente de los bits de `FLAGS` |

**`astroquery` no se usa.** Su resolución de nombres apunta por defecto a los
hosts de Estrasburgo, y por eso Sesame daba timeouts. Las consultas van con
`urllib` + `certifi` directo al TAP.

**Lo que entrega:** funciones puras en `core/` — reciben arrays, devuelven
arrays. Nada de `core/` abre la red ni sabe que existe una web. La única
excepción es `core/fetch_targets.py`, que es un script de mantenimiento.

**Trampas ya documentadas:**
- **No restar imágenes de distinta longitud de onda.** Solo mismo detector y λ parecida, y después de alinear por WCS.
- Las coordenadas del enunciado para WISE 0855 están a **21.4 píxeles** del objeto en la era SPHEREx. Apuntar ahí no da error: da cielo vacío que parece normal.
- El significado de cada bit de `FLAGS` **se saca del Explanatory Supplement, no se adivina**.

Detalle completo en [`core/README.md`](core/README.md) y [`docs/ciencia.md`](docs/ciencia.md).

---

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| Datos pesados y consultas lentas | Caché compacta, precálculo de los 4 objetivos, carga progresiva |
| Cambios en la API de IRSA | Aislar todo el acceso a datos en un solo módulo |
| Pocas épocas por banda | Medir primero cuántas observaciones tiene cada objetivo |
| Objetos con movimiento propio medidos en la posición equivocada | Aceptar movimiento propio en las herramientas y comprobarlo visualmente |
| Interpretación científica incorrecta (sobre todo combinar detectores) | Revisión por alguien que conozca el instrumento |
| Gasto descontrolado si se agrega un agente de IA | Límites por IP, tope de gasto, la web funciona sin él |

---

## 10. Pendientes abiertos

- [x] ~~Coordenadas verificadas de **eps Ind B** y **R Dra**~~ → hecho en la tarea 6. SIMBAD **sí responde**: el problema no era la red sino el certificado TLS y un host que ya no existe. Ver sección 8.1.
- [x] ~~Verificar el **movimiento propio** y la **época** de las coordenadas de WISE 0855~~ → hecho y comprobado con una prueba automática.
- [x] ~~Tabla de cobertura de los otros 3 objetivos~~ → hecho en la tarea 7: `config/coverage.yaml`. Los 4 objetivos tienen cobertura de los 6 detectores.
- [x] ~~Significado de cada bit de `FLAGS`~~ → hecho en la tarea 8: `config/flags.yaml`, 23 bits del Explanatory Supplement. Quedan 9 bits sin documentar en la propia fuente.
- [x] ~~Confirmar si algún rango de longitud de onda se solapa entre detectores~~ → **no se solapan**, se encadenan: 0.75–5.01 µm sin huecos, con costuras de ~0.02 µm. Ver `docs/ciencia.md` sección 3.4.
- [x] ~~Probar la descarga y extracción de espectros con datos reales~~ → hecho con 18 recortes de WISE 0855. Funciona donde el objeto domina (D5–D6); en el azul lo que se mide es una fuente mezclada. Ver `docs/ciencia.md` 7.3.
- [x] Fecha límite del hackathon: **15 de noviembre de 2026**.
- [x] Nombre del proyecto: **HackatonNASA**.
- [ ] Stack del frontend (lo define B). Backend: Python + FastAPI.
- [ ] Volcar el reparto de roles a `docs/EQUIPO.md` (los roles ya están confirmados: ver sección 8).

## 11. Estado actual

- [x] Consulta TAP a IRSA funcionando (WISE 0855: 256 observaciones, 27 fechas).
- [x] Notebook `core/fase0_spherex_explorar_fits.ipynb`: exploración de las extensiones del FITS.
- [x] Repo en GitHub con una rama por persona: `ciencias`, `front` y `back`.
- [x] **Astrometría de los 4 objetivos** (`config/targets.yaml`) con RA, Dec, época, movimiento propio, paralaje y bibcode de cada medición.
- [x] **`core/targets.py`**: funciones puras que propagan una posición a la fecha de cada observación. 10 pruebas en `core/test_targets.py`, todas pasan.
- [x] **Bits de `FLAGS`** (`config/flags.yaml`) y `core/flags.py` para decodificarlos y aplicar las máscaras que recomienda el documento. 26 pruebas en `core/test_flags.py`, todas pasan.
- [x] **Cobertura de los 4 objetivos** (`config/coverage.yaml`): observaciones, fechas, detectores y longitud de onda por detector.
- [x] **`core/align.py`**: alineación por WCS con corrección de movimiento propio (tarea 21). 26 pruebas, incluido el criterio de aceptación y la contraprueba de que sin corregir no centra.
- [x] Notebook de Fase 0 movido a `core/` (tarea 5).
- [x] **`core/subtract.py`**: resta de cuadros comparables, apilado ponderado y detección de dipolo (tarea 22). 25 pruebas.
- [x] **`core/spectrum.py`** y **`core/bands.py`**: espectros, las 102 bandas y curvas de luz (tarea 23). 34 pruebas. Verificado con 18 recortes reales de WISE 0855: a 4.96 µm el flujo reproduce la fotometría W2 publicada con 1 % de diferencia.
- [x] CI en GitHub Actions: 130 pruebas en cada push y PR.
- [ ] Todo lo demás del roadmap (Fases 1 a 6).

> **Corrección:** las versiones anteriores de este README daban por hecho un
> módulo `spherex_espectros.py` con caché compacta, fotometría de apertura y
> combinación ponderada, "probado con datos sintéticos". **Ese archivo nunca
> existió** en el repositorio, en ningún commit del historial. La funcionalidad
> hay que escribirla, y va partida en `align.py`, `subtract.py` y `spectrum.py`,
> que es como la piden las tareas 21, 22 y 23 del Tablero.

## 12. Cómo ejecutar lo que ya existe

```bash
pip install -r requirements.txt
```

`astroquery` **no** hace falta y conviene no usarlo: su resolución de nombres
apunta a hosts de SIMBAD que ya no responden (ver sección 8.1).

### Astrometría de los objetivos

```bash
python core/targets.py            # tabla resumen de los 4 objetivos
python core/test_targets.py       # 10 pruebas, incluida la de la época
python core/fetch_targets.py      # regenera config/targets.yaml desde SIMBAD
```

Desde código, para saber dónde apuntar en una fecha dada:

```python
import core.targets as t
ra, dec = t.target_position("wise_0855", 61174.0)   # MJD del header FITS
```

### Notebook de exploración

Abre `core/fase0_spherex_explorar_fits.ipynb` y ejecuta las celdas **en orden**: el
objetivo, la consulta TAP y el cutout deben correrse antes de las celdas que
usan `coord`, `obs` y `hdul`.

## 13. Fuentes

- [IRSA · SPHEREx Data Access](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/)
- [IRSA · SPHEREx Data Products](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/)
- [IRSA · Tutorial de cutouts](https://caltech-ipac.github.io/irsa-tutorials/spherex-cutouts/)
- [SPHEREx Explanatory Supplement](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp_QR.pdf)
- [Spectral Map Making with SPHEREx (arXiv)](https://arxiv.org/pdf/2603.25790)

## 14. Glosario

- **RA / Dec:** ascensión recta y declinación; las coordenadas del cielo.
- **FITS / MEF:** formato de archivo estándar de la astronomía; MEF es el que contiene varias extensiones.
- **Cutout:** recorte pequeño de una imagen grande alrededor de una posición.
- **WCS:** información que relaciona píxeles con coordenadas del cielo (y, aquí, con longitud de onda).
- **FLAGS:** máscara de calidad por píxel, con un bit por cada tipo de problema.
- **Movimiento propio:** desplazamiento aparente de una estrella o enana en el cielo con los años.
