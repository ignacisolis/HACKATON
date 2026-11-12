// Catálogo de bits de FLAGS para el panel de máscaras. Fuente: config/flags.yaml (Tabla 16 del
// Explanatory Supplement SSDC-DP-017 v2.0 + header FITS MP_*). Solo se usa para AGRUPAR y
// describir: los conteos y los nombres que se muestran vienen del backend.
import type { FlagCount } from '../../api/types'

/**
 * - photometry: en la lista de enmascarado para fotometría (mask_sets.photometry). El backend los
 *   excluye al medir flujo y son los que deciden `quality` / `flagged_fraction`.
 * - contamination: defecto o artefacto que el documento NO excluye de la fotometría (solo del fondo,
 *   o de ninguna lista). Se miran a ojo.
 * - info: informativos, no son defectos (SOURCE es la máscara de fuentes conocidas).
 * - unknown: bit sin significado en ninguna de las dos fuentes.
 */
export type BitGroup = 'photometry' | 'contamination' | 'info' | 'unknown'
export const GROUP_ORDER: BitGroup[] = ['photometry', 'contamination', 'info', 'unknown']

export interface BitInfo {
  bit: number
  group: BitGroup
  deprecated?: boolean
}

export const BITS: Record<string, BitInfo> = {
  TRANSIENT: { bit: 0, group: 'contamination' },
  OVERFLOW: { bit: 1, group: 'contamination' },
  SUR_ERROR: { bit: 2, group: 'photometry' },
  PHANTOM: { bit: 4, group: 'info' },
  REFERENCE: { bit: 5, group: 'info' },
  NONFUNC: { bit: 6, group: 'photometry' },
  DICHROIC: { bit: 7, group: 'contamination' },
  MISSING_DATA: { bit: 9, group: 'photometry' },
  HOT: { bit: 10, group: 'photometry' },
  COLD: { bit: 11, group: 'photometry' },
  FULLSAMPLE: { bit: 12, group: 'info' },
  PHANMISS: { bit: 14, group: 'contamination' },
  NONLINEAR: { bit: 15, group: 'photometry' },
  PERSIST: { bit: 17, group: 'photometry' },
  OUTLIER: { bit: 19, group: 'contamination' },
  CROSSTALK: { bit: 20, group: 'contamination' },
  SOURCE: { bit: 21, group: 'info' },
  GHOST: { bit: 22, group: 'contamination' },
  GHOST_FPA: { bit: 23, group: 'contamination', deprecated: true },
  GHOST_EXT: { bit: 24, group: 'contamination' },
  STREAK: { bit: 25, group: 'contamination' },
  BLOOM: { bit: 26, group: 'photometry' },
  SNOWBALL: { bit: 27, group: 'photometry' },
  HALO: { bit: 28, group: 'photometry' },
  SATELLITE_HALO: { bit: 29, group: 'photometry' },
}

/** El header FITS abrevia algunos nombres en las tarjetas L2 N_* (p. ej. N_MISSING). */
const ALIASES: Record<string, string> = { MISSING: 'MISSING_DATA' }

export function canonicalName(name: string): string {
  const up = name.toUpperCase()
  return ALIASES[up] ?? up
}

export function bitInfo(name: string, bit?: number): BitInfo | null {
  const byName = BITS[canonicalName(name)]
  if (byName) return byName
  if (bit != null) for (const info of Object.values(BITS)) if (info.bit === bit) return info
  return null
}

export function bitGroup(name: string, bit?: number): BitGroup {
  return bitInfo(name, bit)?.group ?? 'unknown'
}

/** ¿El bit lo excluye la máscara de fotometría? (lo que vuelve `suspect` un píxel del objetivo) */
export const isPhotometryMasked = (name: string) => bitGroup(name) === 'photometry'

export interface CountGroup {
  group: BitGroup
  rows: FlagCount[]
}

/** Agrupa las cuentas del recorte en el orden de GROUP_ORDER, de más a menos píxeles. Omite grupos vacíos. */
export function groupCounts(counts: FlagCount[]): CountGroup[] {
  const by = new Map<BitGroup, FlagCount[]>()
  for (const c of counts) {
    const g = bitGroup(c.name, c.bit)
    if (!by.has(g)) by.set(g, [])
    by.get(g)!.push(c)
  }
  return GROUP_ORDER
    .filter(g => by.has(g))
    .map(g => ({ group: g, rows: [...by.get(g)!].sort((a, b) => b.pixels - a.pixels || a.bit - b.bit) }))
}

/** Prende o apaga una capa en la lista de la vista, sin duplicar. */
export function toggleMask(active: string[], name: string): string[] {
  return active.includes(name) ? active.filter(n => n !== name) : [...active, name]
}

/** Bits del píxel del objetivo que además se pueden ofrecer como capa en este recorte. */
export function targetLayers(atTarget: string[] | undefined, layers: string[]): string[] {
  if (!atTarget?.length) return []
  return layers.filter(l => atTarget.includes(l))
}

/** Cuentas del header (exposición completa) ordenadas, sin ceros. */
export function fullFrameRows(full: Record<string, number>): { name: string; pixels: number }[] {
  return Object.entries(full)
    .filter(([, n]) => n > 0)
    .map(([name, pixels]) => ({ name, pixels }))
    .sort((a, b) => b.pixels - a.pixels)
}

export const FULL_FRAME_PIXELS = 2040 * 2040
