// Lógica del panel de ciencia que no es dibujo: qué puntos se muestran, rangos por detector,
// referencias moleculares, curva de luz y clasificación de errores. Pura (spectrum.test.ts).
import { ApiError } from '../../api/client'
import type { Detector, LightCurveResponse, Quality, SpectrumPoint } from '../../api/types'
import { DETECTORS } from '../../api/types'
import { extentWithErrors } from './chart'

export type FluxScale = 'linear' | 'log'

/** Eje x del espectro, en µm: SPHEREx cubre 0.75–5.0 µm; un poco de aire a cada lado. */
export const WL_DOMAIN: [number, number] = [0.7, 5.1]

export const detColor = (d: Detector | string) => `var(--${d.toLowerCase()})`

/** Puntos que se dibujan: los 'bad' solo si el usuario los pide; en log, solo flujo > 0. */
export function plottable(points: SpectrumPoint[], o: { showBad: boolean; scale: FluxScale }) {
  const shown: SpectrumPoint[] = []
  let hiddenBad = 0, hiddenNonPositive = 0
  for (const p of points) {
    if (!isFinite(p.flux) || !isFinite(p.wavelength_um)) continue
    if (p.quality === 'bad' && !o.showBad) { hiddenBad++; continue }
    if (o.scale === 'log' && p.flux <= 0) { hiddenNonPositive++; continue }
    shown.push(p)
  }
  shown.sort((a, b) => a.wavelength_um - b.wavelength_um)
  return { shown, hiddenBad, hiddenNonPositive }
}

/** Dominio del eje de flujo para los puntos visibles. */
export const fluxDomain = (pts: SpectrumPoint[], scale: FluxScale) =>
  extentWithErrors(pts.map(p => ({ v: p.flux, err: p.flux_err })), scale)

/** Tramo de λ que cubre cada detector (incluyendo medio ancho de banda a cada lado), en orden D1…D6.
 *  Sirve para pintar de fondo dónde están las costuras entre detectores (docs/ciencia.md 3.5). */
export function detectorRanges(points: SpectrumPoint[]): { detector: Detector; min: number; max: number }[] {
  const acc = new Map<Detector, { min: number; max: number }>()
  for (const p of points) {
    if (!isFinite(p.wavelength_um)) continue
    const half = isFinite(p.bandwidth_um) ? p.bandwidth_um / 2 : 0
    const r = acc.get(p.detector) ?? { min: Infinity, max: -Infinity }
    r.min = Math.min(r.min, p.wavelength_um - half)
    r.max = Math.max(r.max, p.wavelength_um + half)
    acc.set(p.detector, r)
  }
  return DETECTORS.filter(d => acc.has(d)).map(d => ({ detector: d, ...acc.get(d)! }))
}

/** ¿Es el punto la banda que está mirando el video? Sin detector en la vista, alcanza con la banda. */
export const isSelected = (p: SpectrumPoint, band: number | null, det: Detector | null) =>
  band != null && p.band === band && (det == null || p.detector === det)

export const pointKey = (p: SpectrumPoint) => `${p.detector}-${p.band}-${p.wavelength_um}`

/** Rasgos moleculares del infrarrojo cercano, para orientarse en el espectro.
 *  (referencia general, aproximada): posiciones redondeadas de bandas anchas conocidas, no líneas
 *  medidas ni ajustadas a este objeto. Se muestran solo si el usuario prende el toggle. */
export interface MolecularRef { id: string; label: string; um: number; ice?: boolean }
export const MOLECULAR_REFS: MolecularRef[] = [
  { id: 'h2o-1.4', label: 'H₂O', um: 1.4 },
  { id: 'ch4-1.6', label: 'CH₄', um: 1.6 },
  { id: 'h2o-1.9', label: 'H₂O', um: 1.9 },
  { id: 'ch4-2.2', label: 'CH₄', um: 2.2 },
  { id: 'co-2.3', label: 'CO', um: 2.3 },
  { id: 'h2o-2.7', label: 'H₂O', um: 2.7 },
  { id: 'h2o-ice-3.0', label: 'H₂O', um: 3.0, ice: true },
  { id: 'ch4-3.3', label: 'CH₄', um: 3.3 },
  { id: 'co2-4.26', label: 'CO₂', um: 4.26 },
  { id: 'co-4.6', label: 'CO', um: 4.6 },
]

export interface LcRow { mjd: number; flux: number; err: number }

/** Arrays paralelos de /api/lightcurve → filas ordenadas por fecha, sin valores no finitos. */
export function lightCurveRows(lc: LightCurveResponse): LcRow[] {
  const n = Math.min(lc.mjds.length, lc.flux.length)
  const rows: LcRow[] = []
  for (let i = 0; i < n; i++) {
    const mjd = lc.mjds[i], flux = lc.flux[i], err = lc.flux_err[i]
    if (!isFinite(mjd) || !isFinite(flux)) continue
    rows.push({ mjd, flux, err: isFinite(err) && err > 0 ? err : 0 })
  }
  return rows.sort((a, b) => a.mjd - b.mjd)
}

export type ErrorKind = 'not_implemented' | 'network' | 'error'

/** 501 / not_implemented = el backend todavía no tiene la función de ciencia (rama `ciencias`). */
export function classifyError(e: unknown): ErrorKind {
  if (e instanceof ApiError) {
    if (e.status === 501 || e.code === 'not_implemented') return 'not_implemented'
    if (e.status === 0) return 'network'
  }
  return 'error'
}

export const QUALITIES: Quality[] = ['ok', 'suspect', 'bad']
