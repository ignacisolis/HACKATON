"""Decodificacion de la capa FLAGS de las imagenes espectrales de SPHEREx.

Rol C (Ciencia) - tarea 8 del Tablero.

Funciones puras: reciben arrays, devuelven arrays. El significado de cada bit
sale de config/flags.yaml, transcrito del Explanatory Supplement.

Lo que hay que saber antes de usar esto
---------------------------------------
No existe "la mascara de pixeles malos". El documento da DOS listas distintas
y la diferencia no es un detalle:

  - para estimar el FONDO se enmascara SOURCE, TRANSIENT, OVERFLOW y OUTLIER,
    porque lo que se busca es cielo limpio;
  - para medir FOTOMETRIA esos cuatro NO se enmascaran, porque SOURCE marca
    justamente los pixeles de la fuente que se quiere medir.

SOURCE (bit 21) aparece en ~41 % de los pixeles. Enmascararlo "por si acaso"
borra el objetivo y deja un espectro de cielo vacio.

Uso
---
    >>> import core.flags as f
    >>> f.decode(0b1010)                      # que bits trae un valor
    ['OVERFLOW', 'SUR_ERROR']
    >>> malos = f.mask_for(hdul["FLAGS"].data, "photometry")
    >>> flujo = imagen[~malos].sum()
    >>> f.bit_counts(hdul["FLAGS"].data)      # para el panel de metadata (C6)
"""
from __future__ import annotations

import functools
from pathlib import Path

import numpy as np
import yaml

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "flags.yaml"


# --------------------------------------------------------------------------
# Carga de configuracion
# --------------------------------------------------------------------------

@functools.lru_cache(maxsize=4)
def load_config(path=None):
    """Lee flags.yaml. Cacheado: no cambia mientras corre el proceso."""
    p = Path(path) if path else DEFAULT_CONFIG
    if not p.is_file():
        raise FileNotFoundError("No encuentro " + str(p))
    with p.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@functools.lru_cache(maxsize=4)
def _name_to_bit(path=None):
    return {spec["name"]: bit for bit, spec in load_config(path)["bits"].items()}


@functools.lru_cache(maxsize=4)
def _bit_to_name(path=None):
    return {bit: spec["name"] for bit, spec in load_config(path)["bits"].items()}


def known_bits(path=None):
    """Bits con significado documentado, ordenados."""
    return sorted(_bit_to_name(path))


def unassigned_bits(path=None):
    """Bits que NO estan en la tabla del documento: sin significado conocido."""
    return list(load_config(path)["unassigned_bits"])


def bit_of(name, path=None):
    """Numero de bit de un nombre simbolico. 'SOURCE' -> 21."""
    try:
        return _name_to_bit(path)[name]
    except KeyError:
        raise KeyError(
            "Flag desconocido: " + repr(name) + ". Conocidos: "
            + repr(sorted(_name_to_bit(path)))
        ) from None


def name_of(bit, path=None):
    """Nombre simbolico de un bit. 21 -> 'SOURCE'."""
    try:
        return _bit_to_name(path)[bit]
    except KeyError:
        raise KeyError(
            "El bit " + str(bit) + " no esta documentado en el Explanatory "
            "Supplement. Sin significado conocido."
        ) from None


def describe(name_or_bit, path=None):
    """Bloque completo de un flag: descripcion, nota y etapa."""
    bit = name_or_bit if isinstance(name_or_bit, int) else bit_of(name_or_bit, path)
    return load_config(path)["bits"][bit]


# --------------------------------------------------------------------------
# Decodificacion: la parte pura
# --------------------------------------------------------------------------

def bitmask(names, path=None):
    """Entero con los bits de `names` prendidos. Puro.

    >>> bitmask(["TRANSIENT", "SOURCE"]) == (1 << 0) | (1 << 21)
    True
    """
    value = 0
    for n in names:
        value |= 1 << bit_of(n, path)
    return value


def decode(value, path=None):
    """Nombres de los flags prendidos en un valor entero. Puro.

    Los bits prendidos que no estan documentados se devuelven como
    'BIT_<n>', para que salten a la vista en vez de desaparecer.
    """
    value = int(value)
    out = []
    for bit in range(32):
        if value & (1 << bit):
            out.append(_bit_to_name(path).get(bit, "BIT_" + str(bit)))
    return out


def has_any(flags, names, path=None):
    """Array booleano: True donde el pixel tiene alguno de `names`. Puro."""
    return (np.asarray(flags).astype(np.uint32) & np.uint32(bitmask(names, path))) != 0


def has_all(flags, names, path=None):
    """Array booleano: True donde el pixel tiene TODOS los `names`. Puro."""
    m = np.uint32(bitmask(names, path))
    return (np.asarray(flags).astype(np.uint32) & m) == m


def has_bit(flags, bit):
    """Array booleano para un bit suelto, documentado o no. Puro."""
    return (np.asarray(flags).astype(np.uint32) & np.uint32(1 << int(bit))) != 0


# --------------------------------------------------------------------------
# Mascaras recomendadas por el documento
# --------------------------------------------------------------------------

def mask_sets(path=None):
    """Nombres de los conjuntos de mascara disponibles."""
    return list(load_config(path)["mask_sets"].keys())


def mask_flags(purpose, path=None):
    """Lista de flags que el documento recomienda enmascarar para `purpose`."""
    sets = load_config(path)["mask_sets"]
    if purpose not in sets:
        raise KeyError(
            "Proposito desconocido: " + repr(purpose) + ". Disponibles: "
            + repr(list(sets)) + ". No inventar una mascara propia sin anotar por que."
        )
    return list(sets[purpose]["flags"])


def mask_for(flags, purpose, path=None):
    """Array booleano: True donde el pixel se debe EXCLUIR. Puro.

    `purpose` es 'photometry' o 'background'. No hay default a proposito: elegir
    mal cambia el resultado en silencio, asi que quien llama lo dice explicito.
    """
    return has_any(flags, mask_flags(purpose, path), path)


def good_pixels(flags, purpose, path=None):
    """El complemento de mask_for: True donde el pixel SI se puede usar."""
    return ~mask_for(flags, purpose, path)


# --------------------------------------------------------------------------
# Resumen para el panel de metadata (consideracion C6)
# --------------------------------------------------------------------------

def bit_counts(flags, path=None, include_zero=False):
    """Cuantos pixeles tiene cada flag prendido, y que fraccion del total.

    Devuelve una lista de dicts ordenada de mas a menos frecuente, lista para
    alimentar el panel de metadata y la capa de mascaras del frontend.
    """
    arr = np.asarray(flags).astype(np.uint32)
    total = arr.size
    rows = []
    for bit in known_bits(path):
        n = int(np.count_nonzero(arr & np.uint32(1 << bit)))
        if n or include_zero:
            spec = load_config(path)["bits"][bit]
            rows.append({
                "bit": bit,
                "name": spec["name"],
                "label": spec.get("label", spec["name"]),
                "pixels": n,
                "fraction": n / total if total else 0.0,
            })
    rows.sort(key=lambda r: -r["pixels"])
    return rows


def undocumented_bits_present(flags, path=None):
    """Bits prendidos que el documento no describe.

    Si esto devuelve algo, el Explanatory Supplement que tenemos quedo viejo
    respecto de los datos. Es una alarma, no un detalle.
    """
    arr = np.asarray(flags).astype(np.uint32)
    documented = known_bits(path)
    found = []
    for bit in range(32):
        if bit in documented:
            continue
        n = int(np.count_nonzero(arr & np.uint32(1 << bit)))
        if n:
            found.append({"bit": bit, "pixels": n, "fraction": n / arr.size})
    return found


def source_doc(path=None):
    """De donde salio esta tabla, para citarla en la presentacion."""
    return load_config(path)["source"]


if __name__ == "__main__":
    cfg = load_config()
    src = cfg["source"]
    print(src["document"] + " " + src["doc_id"] + " v" + src["version"]
          + " (" + src["date"] + "), " + src["table"])
    print()
    print("{:>4}  {:<16} {}".format("bit", "nombre", "etiqueta"))
    print("-" * 64)
    for bit in known_bits():
        spec = cfg["bits"][bit]
        print("{:>4}  {:<16} {}".format(bit, spec["name"], spec.get("label", "")))
    print()
    print("Sin significado conocido: " + repr(unassigned_bits()))
    for purpose in mask_sets():
        print("\nmascara " + purpose + " (" + str(len(mask_flags(purpose))) + " flags):")
        print("  " + ", ".join(mask_flags(purpose)))
