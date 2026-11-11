"""Genera config/bands.yaml: las 102 bandas de SPHEREx.

Rol C (Ciencia). Apoya las consideraciones C2 y C3 del enunciado (entregar las
102 bandas y dejar que el usuario elija una) y cierra una pregunta que quedaba
abierta en contracts/api.md: como se numeran.

Sin red: lee los rangos por detector de config/coverage.yaml, que ya estan
medidos contra IRSA y son identicos en los 4 objetivos, o sea constantes del
instrumento.

    python core/make_bands.py
    python core/make_bands.py --check     # verifica que el YAML este al dia

DE DONDE SALE EL ESPACIADO
--------------------------
No es lineal en longitud de onda: es logaritmico, a poder resolvente constante.

Se deduce de medir 6 exposiciones reales consecutivas de D2 sobre R Dra. La
longitud de onda en el objetivo iba 1.4017, 1.4359, 1.4706, 1.5067, 1.5431 y
1.5806 um, y el ancho de banda 0.0336, 0.0347, 0.0357, 0.0368, 0.0376 y 0.0383.

El ancho CRECE con la longitud de onda, y lambda/ancho da 41.7 en el extremo
azul y 41.3 en el rojo: constante, e igual al energy_resolvingpower que publica
IRSA para D2, 41.4. Y el cociente entre lambdas consecutivas tambien es
constante, 1.0244, que es justo 1 + 1/41.4.

O sea: cada exposicion consecutiva avanza UN canal, y los canales estan
espaciados por un factor fijo. Es un espectrometro de R constante.

CUANTOS CANALES POR DETECTOR
----------------------------
La mision publica 102 bandas, o sea 17 por detector. Se puede comprobar: con
R constante, el numero de canales que caben en el rango de un detector es
ln(lambda_max/lambda_min) / ln(1 + 1/R). Da entre 16.0 y 16.9 segun el
detector, consistente con 17 dentro de la precision de los bordes que publica
IRSA. Se usa 17, que es el numero oficial y el que da 102 exacto.
"""
from __future__ import annotations

import argparse
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
COVERAGE = RAIZ / "config" / "coverage.yaml"
SALIDA = RAIZ / "config" / "bands.yaml"

# Numero oficial de canales por detector. 6 x 17 = las 102 bandas de la mision.
CHANNELS_PER_DETECTOR = 17


def rangos_por_detector():
    """Rango de longitud de onda y R de cada detector, desde coverage.yaml.

    Son constantes del instrumento: identicas en los 4 objetivos. Si algun dia
    difieren, esto falla en vez de elegir una al azar.
    """
    cov = yaml.safe_load(COVERAGE.read_text(encoding="utf-8"))["coverage"]
    vistos = {}
    for objetivo, c in cov.items():
        for det, d in c["detectors"].items():
            if d["wavelength_min_um"] is None:
                continue
            clave = (round(d["wavelength_min_um"], 4),
                     round(d["wavelength_max_um"], 4),
                     round(d["resolving_power"], 1))
            vistos.setdefault(det, {}).setdefault(clave, []).append(objetivo)

    rangos = {}
    for det in sorted(vistos):
        if len(vistos[det]) > 1:
            raise SystemExit(
                "El detector " + det + " tiene rangos distintos segun el objetivo: "
                + repr(vistos[det]) + ". Son constantes del instrumento, asi que "
                "esto hay que entenderlo antes de generar las bandas."
            )
        rangos[det] = next(iter(vistos[det]))
    return rangos


def construir_bandas(rangos, n_canales=CHANNELS_PER_DETECTOR):
    """Las bandas, numeradas de 1 a 102 por longitud de onda creciente."""
    bandas = []
    indice = 0
    for det in sorted(rangos):   # D1..D6 ya quedan en orden de lambda creciente
        lo, hi, R = rangos[det]
        # Espaciado logaritmico: lambda_k = lo * (hi/lo)^(k/n)
        factor = (hi / lo) ** (1.0 / n_canales)
        for k in range(n_canales):
            indice += 1
            b_lo = lo * factor ** k
            b_hi = lo * factor ** (k + 1)
            centro = math.sqrt(b_lo * b_hi)   # centro geometrico, no aritmetico
            bandas.append({
                "band": indice,
                "detector": det.replace("SPHEREx-", ""),
                "channel": k + 1,
                "wavelength_um": round(centro, 5),
                "wavelength_min_um": round(b_lo, 5),
                "wavelength_max_um": round(b_hi, 5),
                "bandwidth_um": round(b_hi - b_lo, 5),
                "resolving_power": R,
            })
    return bandas


def canales_implicados(rangos, n_canales=CHANNELS_PER_DETECTOR):
    """Cuantos canales caben en cada detector segun su R. Para documentar."""
    out = {}
    for det, (lo, hi, R) in sorted(rangos.items()):
        n = math.log(hi / lo) / math.log(1.0 + 1.0 / R)
        out[det.replace("SPHEREx-", "")] = round(n, 2)
    return out


def render(rangos, bandas):
    implicados = canales_implicados(rangos)
    cab = (
        "# config/bands.yaml\n"
        "#\n"
        "# Las 102 bandas de SPHEREx: 6 detectores x 17 canales.\n"
        "#\n"
        "# GENERADO: no editar a mano. Se regenera con:\n"
        "#     python core/make_bands.py\n"
        "#\n"
        "# Numeradas de 1 a 102 por longitud de onda creciente. Esta es la\n"
        "# convencion del proyecto, y es la que responde la pregunta abierta de\n"
        "# contracts/api.md sobre como se numeran las bandas.\n"
        "#\n"
        "# EL ESPACIADO ES LOGARITMICO, NO LINEAL\n"
        "# SPHEREx es un espectrometro de poder resolvente constante, asi que el\n"
        "# ancho de banda crece con la longitud de onda. Medido en 6 exposiciones\n"
        "# reales consecutivas de D2: lambda iba 1.4017 a 1.5806 um y el ancho de\n"
        "# 0.0336 a 0.0383, con lambda/ancho constante en ~41.4, que es justo el\n"
        "# resolving power que publica IRSA. El cociente entre lambdas\n"
        "# consecutivas tambien es constante, 1.0244 = 1 + 1/41.4.\n"
        "#\n"
        "# Por eso el centro de cada banda es el centro GEOMETRICO de sus bordes,\n"
        "# no el aritmetico.\n"
        "#\n"
        "# CUANTOS CANALES POR DETECTOR\n"
        "# Con R constante caben ln(hi/lo)/ln(1+1/R) canales en cada detector:\n"
        + "".join("#     " + d + ": " + format(n, ".2f") + "\n"
                  for d, n in implicados.items())
        + "# Entre 16.0 y 16.9, consistente con 17 dentro de la precision de los\n"
        "# bordes que publica IRSA. Se usa 17, que es el numero oficial y el que\n"
        "# da 102 exacto.\n"
        "\n"
        "schema_version: 1\n"
        "generated_utc: " + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "\n"
        "generator: core/make_bands.py\n"
        "source: rangos por detector de config/coverage.yaml, medidos contra IRSA\n"
        "channels_per_detector: " + str(CHANNELS_PER_DETECTOR) + "\n"
        "n_bands: " + str(len(bandas)) + "\n"
        "spacing: logarithmic (constant resolving power)\n"
        "wavelength_min_um: " + format(bandas[0]["wavelength_min_um"], ".5f") + "\n"
        "wavelength_max_um: " + format(bandas[-1]["wavelength_max_um"], ".5f") + "\n"
        "\n"
    )
    cuerpo = yaml.dump({"bands": bandas}, allow_unicode=True, sort_keys=False,
                       default_flow_style=False, width=100)
    return cab + cuerpo


def main():
    ap = argparse.ArgumentParser(description="Genera config/bands.yaml.")
    ap.add_argument("--check", action="store_true",
                    help="no escribe; falla si el YAML no coincide con lo generado")
    args = ap.parse_args()

    rangos = rangos_por_detector()
    bandas = construir_bandas(rangos)
    if len(bandas) != 102:
        raise SystemExit("salieron " + str(len(bandas)) + " bandas, se esperaban 102")
    texto = render(rangos, bandas)

    if args.check:
        if not SALIDA.is_file():
            raise SystemExit("falta " + str(SALIDA) + ": corre python core/make_bands.py")
        actual = yaml.safe_load(SALIDA.read_text(encoding="utf-8"))
        if actual.get("bands") != bandas:
            raise SystemExit(
                "config/bands.yaml no coincide con lo que genera este script. "
                "Regeneralo con: python core/make_bands.py"
            )
        print("config/bands.yaml al dia: " + str(len(bandas)) + " bandas")
        return

    SALIDA.write_text(texto, encoding="utf-8")
    print("Escrito " + str(SALIDA) + " (" + str(len(bandas)) + " bandas, "
          + format(bandas[0]["wavelength_min_um"], ".3f") + " a "
          + format(bandas[-1]["wavelength_max_um"], ".3f") + " um)")


if __name__ == "__main__":
    main()
