# Reglas de `core/` — para humanos y para IAs

Carpeta del rol **C · Ciencia** (Nacho), rama `ciencias`.

## La regla principal

**Funciones puras: reciben valores, devuelven valores.** Nada en `core/` abre la
red, lee configuración del servidor, escribe archivos ni sabe que existe una
web. Si una función necesita datos de IRSA, los recibe como argumento.

Dos excepciones, y son scripts de mantenimiento que se corren a mano, nunca en
la ruta de ejecución de la web:

- `fetch_targets.py` — consulta SIMBAD, escribe `config/targets.yaml`
- `fetch_coverage.py` — consulta IRSA, escribe `config/coverage.yaml`

## No toques

- `backend/`, `frontend/`, `contracts/` — son de Camilo, Bruno y de los tres.
  Si hace falta cambiar el contrato, se avisa antes.
- `config/targets.yaml`, `config/coverage.yaml` — **generados**. Se editan
  regenerándolos, no a mano.
- `config/flags.yaml` — transcrito a mano del Explanatory Supplement. Si lo
  tocás, citá la página.

## Antes de dar un número por bueno

Este proyecto ya tuvo cuatro casos donde algo "obvio" era falso. El patrón se
repite: **el error no se ve, porque el resultado equivocado parece plausible.**

1. Las coordenadas del enunciado para WISE 0855 son de 2010. Apuntar ahí no da
   error: da un recorte lleno de estrellas, sin el objetivo.
2. El bit 21 de `FLAGS` parecía un defecto que cubría el 41 % de los píxeles.
   Es `SOURCE`, la máscara de fuentes. Enmascararlo borra el objetivo.
3. "SIMBAD no responde" era un certificado TLS y un host de DNS caído.
4. El README daba por existente un módulo que nunca estuvo en el repo.

De ahí tres hábitos que conviene mantener:

- **Citá la fuente de cada número** en el YAML o en el docstring. Los bibcodes y
  las páginas del documento están para eso.
- **Escribí una prueba que falle si la suposición es falsa.** El ejemplo es
  `test_wise0855_epoch_is_j2000`: no asume que las coordenadas de SIMBAD son
  J2000, lo verifica propagándolas hasta 2010.5 y comparando con la designación
  WISE. Da 0.41″ donde un año de error daría 8.15″.
- **No adivines.** Los 7 bits que ninguna fuente documenta están listados como
  `unassigned_bits`, no inventados. Si una fuente no dice algo, el YAML dice que
  no lo dice.

## Lo que ya funciona

```bash
python core/targets.py            # tabla resumen de los objetivos
python core/flags.py              # bits de FLAGS y las dos máscaras
python core/test_targets.py       # 10 pruebas
python core/test_flags.py         # 35 pruebas
```

## Dos trampas de los datos de SPHEREx

- **No se restan imágenes de distinta longitud de onda.** El filtro varía a lo
  largo del detector, así que cada exposición mide el objetivo en una λ
  concreta. `core.is_comparable()` valida esto y ya funciona.
- **Los 6 detectores no se solapan: se encadenan** (0.75 a 5.01 µm). Así que
  "combinar los 6 detectores para mejorar señal/ruido" no puede ser apilarlos
  sobre la misma banda. La mejora sale de visitas repetidas a la misma banda.

## Dependencias

```bash
pip install numpy astropy pyyaml certifi
```

`astroquery` **no** se usa: su resolución de nombres apunta a hosts de SIMBAD
que ya no responden. Las consultas van con `urllib` + `certifi`.

## Contexto

- [`README.md`](README.md) de la carpeta — cómo correr cada cosa
- [`../docs/ciencia.md`](../docs/ciencia.md) — los hallazgos y sus fuentes
- [`../contracts/api.md`](../contracts/api.md) — la frontera con `backend/`
- [`../docs/EQUIPO.md`](../docs/EQUIPO.md) — roles y dependencias
