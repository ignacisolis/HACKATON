// Datos de detector para el selector. Lógica pura.
import type { CoverageResponse, Detector } from '../../api/types'

/** Rango de λ APROXIMADO de cada detector, en µm (bordes nominales de SPHEREx, coinciden con lo
 *  medido en WISE 0855 en noviembre de 2026: D1 0.744–1.115, D2 1.101–1.630, …). Se muestra con "≈";
 *  para el detector activo se usa el rango medido en los cuadros. Los bordes se solapan apenas:
 *  por eso una banda se elige dentro de un detector y nunca solo por λ. */
export const NOMINAL_RANGE_UM: Record<Detector, [number, number]> = {
  D1: [0.75, 1.11],
  D2: [1.10, 1.63],
  D3: [1.63, 2.42],
  D4: [2.42, 3.83],
  D5: [3.82, 4.42],
  D6: [4.42, 5.00],
}

export interface DetectorCoverage {
  /** fechas (días UTC) con al menos un cuadro de ese detector */
  dates: number
  /** cuadros totales de ese detector */
  frames: number
}

export function detectorCoverage(c: CoverageResponse | null, det: Detector): DetectorCoverage | null {
  if (!c) return null
  return {
    dates: c.dates.filter(d => d.detectors.includes(det)).length,
    frames: c.detectors[det] ?? 0,
  }
}
