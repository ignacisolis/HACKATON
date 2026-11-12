# Pitch y guion del video demo

Tarea 30. Guion de **4 minutos**, con los tiempos, lo que se dice y lo que se
muestra en pantalla. Sirve igual para presentar en vivo o para grabar el video.

> **Regla que no se rompe:** no se afirma nada que no se pueda mostrar. Si el
> backend no está levantado el día de la entrega, se usa el guion alternativo de
> la sección 6, que es honesto y sigue siendo bueno. Presentar fixtures como si
> fueran observaciones de SPHEREx nos descalifica, y con razón.

---

## 1 · El problema (0:00 – 0:30)

> «SPHEREx mapea el cielo entero cada seis meses, en 102 bandas de infrarrojo
> cercano. En ese archivo hay más de mil millones de objetos, que se superponen
> entre sí y cambian de brillo. El dato está público desde el primer día. El
> problema no es el acceso: es que para mirar cómo cambia un punto del cielo hay
> que bajar archivos de 70 megas, entender seis extensiones FITS, mapas de
> longitud de onda por píxel y máscaras de calidad de 32 bits.
>
> Nosotros hicimos la herramienta que falta: escribís coordenadas y ves esa zona
> del cielo como un video en el tiempo.»

**Pantalla:** la página, vacía, con el formulario de coordenadas.

---

## 2 · La demo (0:30 – 2:00)

Es la parte que más se ensaya. Tiene que fluir sin dudar.

| Tiempo | Qué se muestra | Qué se dice |
|---|---|---|
| 0:30 | Escribir **RW Aurigae** o tocar su atajo | «Elegimos RW Aurigae, una estrella variable.» |
| 0:45 | El video corriendo | «Cada cuadro es una visita distinta de SPHEREx. Acá se ve cambiar el brillo.» |
| 1:05 | Selector de **detector y banda** | «102 bandas. El usuario elige con cuál trabajar.» |
| 1:20 | Capa de **máscaras FLAGS** encendida | «Cada bit de calidad se puede prender como capa sobre la imagen.» |
| 1:35 | Panel de **espectro** | «Y el espectro del punto, al instante.» |
| 1:50 | **Copiar la URL** y pegarla en otra pestaña | «La vista entera viaja en la URL: mismas coordenadas, misma banda, mismo zoom. Se comparte un hallazgo con un link.» |

---

## 3 · Lo que nos diferencia (2:00 – 3:15)

Acá está el valor real. **No contar las seis cosas: contar dos o tres bien.**
Elegir según el jurado; las tres primeras son las más fuertes.

### 3.1 · Las coordenadas del enunciado están desactualizadas

> «El propio enunciado da las coordenadas de WISE 0855. Son de 2010. El objeto
> se mueve 8 segundos de arco por año, así que hoy está a **21 píxeles** de ahí.
>
> Y lo peligroso es que apuntar ahí **no da error**: devuelve un recorte de cielo
> que parece perfectamente normal, lleno de estrellas, sin el objeto. Nuestra
> herramienta corrige movimiento propio por fecha de observación, así que apunta
> donde el objeto está ese día.»

**Pantalla:** las dos posiciones marcadas sobre el mismo recorte.

### 3.2 · El movimiento se ve restando, no reproduciendo

> «El enunciado pide hacer visible el movimiento. Lo medimos: dentro de toda la
> ventana de datos de SPHEREx, WISE 0855 se desplaza **1.35 píxeles**. En un
> video eso se ve estático.
>
> Entonces lo resolvimos restando dos épocas alineadas al cielo. Con Epsilon
> Indi B, separadas 525 días, el objeto deja un dipolo: negativo donde estaba,
> positivo donde está. Medido a **72 y 94 sigma**.»

**Pantalla:** la imagen de la resta, con el dipolo.

### 3.3 · Validamos contra fotometría publicada

> «Un espectro que corre no es un espectro correcto. Así que lo contrastamos: a
> 4.96 micrones, nuestro flujo de WISE 0855 reproduce su fotometría WISE
> publicada con **1 % de diferencia**.»

**Pantalla:** el espectro, con el punto comparado.

### 3.4 · Otros, si hay tiempo o preguntan

- **El bit que cubría el 41 % de los píxeles no era un defecto:** es `SOURCE`, la
  máscara de fuentes. Enmascararlo al medir borra el objetivo. En un recorte real
  la máscara correcta deja 790 de 841 píxeles; la equivocada, cero.
- **Las 102 bandas son logarítmicas**, no equiespaciadas, y lo dedujimos midiendo
  seis exposiciones reales. Se validó solo: esas seis caen en bandas consecutivas.
- **R Draconis satura.** Lo habíamos elegido como mejor caso por tener 2.483
  observaciones. Al abrir los archivos, cero píxeles usables. Sirve para el video,
  no para fotometría.

---

## 4 · Lo que no hace (3:15 – 3:40)

**No saltearse esta parte.** Un jurado técnico la valora más que una demo pulida,
y protege de la pregunta incómoda.

> «Tres cosas que todavía no hace.
>
> Por debajo de 3 micrones, el espectro de WISE 0855 no es suyo: es de una fuente
> vecina dentro de la apertura de 15 segundos de arco. Es exactamente el problema
> de superposición que nombra el enunciado, y para resolverlo hace falta ajustar
> PSF en vez de sumar apertura.
>
> La resta no iguala las PSF, así que deja residuos alrededor de las fuentes
> brillantes.
>
> Y las longitudes de onda salen de `WCS-WAVE`, que es una aproximación. Para un
> número publicable hay que usar el producto Spectral WCS.»

---

## 5 · Cierre (3:40 – 4:00)

> «Está todo público, con 164 pruebas automáticas y CI. Las funciones de ciencia
> son puras y reusables: quien quiera armar otra herramienta sobre SPHEREx puede
> importar `core/` y saltearse las trampas que nosotros encontramos a los golpes.
>
> Eso es lo que nos parece que vale más: no la página, sino lo que aprendimos de
> los datos y dejamos escrito con sus fuentes.»

---

## 6 · Guion alternativo, si el backend no está levantado

Cambia **solo** el bloque 2. Todo lo demás se mantiene, porque las mediciones de
la sección 3 son reales y reproducibles desde el repo.

> «Lo que ven ahora es la interfaz con datos de ejemplo: el backend todavía no
> está hosteado. Las mediciones que vamos a mostrar son todas de datos reales de
> SPHEREx y se reproducen con un comando del repositorio.»

Y se muestra la demo corriendo en local contra IRSA, o capturas de los
resultados reales.

**Lo que NO se dice:** «esto es SPHEREx en vivo». No lo es todavía.

---

## 7 · Checklist antes de grabar

- [ ] El backend responde (`/api/health`) — si no, guion alternativo
- [ ] `VITE_API_BASE` puesta y `VITE_USE_FIXTURES` borrada en Vercel
- [ ] Los 4 links `?target=` abren y cargan
- [ ] Ensayar el bloque 2 hasta que salga sin dudar: es el que se mira
- [ ] Tener a mano la resta de eps Ind B ya generada, por si tarda
- [ ] Decir el link de la web y el del repositorio

---

## 8 · Las frases clave, en inglés

Por si se presenta en inglés. El resto del fraseo está en
[`README.en.md`](../README.en.md).

- *"The coordinates in the challenge itself are from 2010. The object is now 21 pixels away — and pointing there doesn't fail, it just quietly returns the wrong patch of sky."*
- *"Across the entire SPHEREx archive, WISE 0855 moves 1.35 pixels. A video shows nothing. Subtracting two epochs shows a dipole at 72 sigma."*
- *"Our spectrum reproduces the object's published WISE photometry to within 1 %."*
- *"The flag covering 41 % of the pixels wasn't a defect — it was the source mask. Masking it deletes the thing you're measuring."*
- *"We're not claiming more than we can show: below 3 microns that spectrum belongs to a neighbour, not to the dwarf."*
