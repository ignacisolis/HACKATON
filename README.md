# Visor web de SPHEREx: el cielo en el tiempo

> Proyecto para el **Hackathon NASA · SPHEREx**. Nombre provisional del proyecto: _por definir_.
> Estado: **Fase 0 (exploración de datos) en curso.** Fecha límite del hackathon: _por definir_.

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

El usuario ingresa las **coordenadas** (ascensión recta y declinación) de una parte del cielo, y la herramienta entrega **una serie de imágenes de ese segmento, reproducida como video**, de modo que sea fácil notar el movimiento de los objetos.

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
| **R Draconis** | Estrella variable evolucionada | Cambio de brillo y espectro |

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

### Movimiento propio (muy importante)
- Las coordenadas de WISE 0855 del enunciado parecen ser de ~2010 (coinciden con su designación WISE). Con ~8″/año de movimiento propio, en 2026 estaría a ~126″, es decir ~20 píxeles de esa posición _(valores por verificar en SIMBAD)_.
- Lo mismo aplica a eps Ind (~4.7″/año). Las herramientas deben aceptar movimiento propio, o se mide cielo vacío.

### Resolución de eps Ind B
- La separación entre las dos enanas cafés es de ~0.72″, muy menor al píxel de ~6.2″: **aparecerán mezcladas como un solo objeto**. No se promete verlas como dos puntos.

### Velocidad
- La consulta TAP a IRSA tardó ~8.6 s para WISE 0855. Los cutouts y la resolución de nombres (Sesame) fueron lo más lento, y Sesame falló con timeouts desde nuestra red.
- Una consulta de varios segundos es demasiado lenta para una web interactiva: hay que **cachear y precalcular**.

### FLAGS
- Un bit domina (el 21, ~41 % de los píxeles). El significado exacto de cada bit **debe tomarse del Explanatory Supplement**; no lo adivinamos.

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

_Las semanas son orientativas y deben ajustarse a la fecha límite real._

### Prioridades si el tiempo aprieta
1. **Imprescindible:** coordenadas → video, selector de banda, URL con coordenadas, los 4 objetos funcionando.
2. **Muy valioso:** restar/sumar imágenes, espectro instantáneo, máscaras de `FLAGS`.
3. **Extra:** combinar detectores, Aladin, cubos precalculados, panel tipo TOPCAT, agente de IA.

---

## 8. División del trabajo (3 personas)

| Rol | Responsable | Es dueño de |
|---|---|---|
| **A · Datos y backend** | _por asignar_ | Acceso a IRSA, caché, API, configuración de versiones, script de actualización, despliegue del backend |
| **B · Frontend y experiencia** | _por asignar_ | Formulario, reproductor, selector de banda, URL, panel de espectro, capa de máscaras, Aladin, despliegue de la web |
| **C · Ciencia y procesamiento** | _por asignar_ | Alineación, imagen de referencia, restas, espectros, combinación de detectores, validación con los 4 objetos, documentación y presentación |

Reglas de trabajo:
- Acordar la API en la primera semana, para que B trabaje con datos falsos mientras A termina el backend real.
- C entrega funciones puras de Python (reciben arrays, devuelven arrays) que A llama desde la API.
- Un solo repositorio con carpetas separadas y ramas por persona; sincronización breve 2 o 3 veces por semana.
- Un responsable de integración (sugerido: A).

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

- [ ] Coordenadas verificadas de **eps Ind B** y **R Dra** (SIMBAD no respondió desde nuestra red).
- [ ] Verificar el **movimiento propio** y la **época** de las coordenadas de WISE 0855.
- [ ] Tabla de cobertura de los otros 3 objetivos (nº de observaciones, fechas, detectores).
- [ ] Significado de cada bit de `FLAGS` (Explanatory Supplement).
- [ ] Confirmar si algún rango de longitud de onda se solapa entre detectores.
- [ ] Probar la descarga y extracción de espectros con datos reales.
- [ ] Fecha límite del hackathon y lenguajes que maneja cada integrante (para fijar el stack, por ejemplo Python + FastAPI y JavaScript).
- [ ] Definir el nombre del proyecto y asignar roles.

## 11. Estado actual

- [x] Consulta TAP a IRSA funcionando (WISE 0855: 256 observaciones, 27 fechas).
- [x] Notebook `fase0_spherex_explorar_fits.ipynb`: exploración de las extensiones del FITS.
- [x] Módulo `spherex_espectros.py`: caché compacta, fotometría de apertura, movimiento propio, combinación ponderada y gráfico (probado con datos sintéticos; la descarga real aún no).
- [ ] Todo lo demás del roadmap (Fases 1 a 6).

## 12. Cómo ejecutar lo que ya existe

```bash
pip install numpy astropy astroquery matplotlib
```

1. Abre `fase0_spherex_explorar_fits.ipynb` y ejecuta las celdas **en orden** (el objetivo, la consulta TAP y el cutout deben correrse antes de las celdas que usan `coord`, `obs` y `hdul`).
2. Para espectros, deja `spherex_espectros.py` junto al notebook y usa:

```python
import spherex_espectros as se
tab  = se.extraer_espectro(coord, obs, max_obs=12, detectores=["D2"])
comb = se.combinar_espectro(tab)
se.graficar_espectro(tab, comb)
```

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
