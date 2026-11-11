// Modo fixtures (VITE_USE_FIXTURES=1): responde con contracts/fixtures/*.json, que son el contrato
// ejecutable. Las imágenes son los 12 PNG de prueba (59×59, un objeto que se mueve en diagonal).
// Los flujos de los fixtures son inventados: sirven para la interfaz, no para ciencia.
import framesRDra from '../../../contracts/fixtures/frames.json'
import framesWise from '../../../contracts/fixtures/frames-sparse.json'
import metaFx from '../../../contracts/fixtures/frame-meta.json'
import spectrumFx from '../../../contracts/fixtures/spectrum.json'
import type {
  CoverageResponse, Detector, Frame, FrameMeta, FramesResponse, ImageOptions,
  LightCurveResponse, SkyQuery, SpectrumResponse, TargetSummary,
} from './types'
import { ApiError, type FramesParams } from './client'

const N_IMG = 12
const delay = <T,>(v: T, ms = 150) => new Promise<T>(r => setTimeout(() => r(v), ms))

const TARGETS: TargetSummary[] = [
  { key: 'eps_ind_b', name: 'Epsilon Indi B (Ba+Bb)', ra: 331.09673, dec: -56.80067, size: 0.1 },
  { key: 'wise_0855', name: 'WISE 0855-0714', ra: 133.7597, dec: -7.24218, size: 0.1 },
  { key: 'rw_aur', name: 'RW Aurigae A', ra: 76.95609, dec: 30.40113, size: 0.1 },
  { key: 'r_dra', name: 'R Draconis', ra: 248.16723, dec: 66.75502, size: 0.1 },
]

export const targets = () => delay(TARGETS)

function baseFrames(q: SkyQuery): FramesResponse {
  const src = ('target' in q && q.target === 'wise_0855') ? framesWise : framesRDra
  return structuredClone(src) as unknown as FramesResponse
}

export function frames(q: SkyQuery, p: FramesParams = {}): Promise<FramesResponse> {
  const r = baseFrames(q)
  r.frames = r.frames
    .map((f, i) => ({ ...f, id: `fx${String(i).padStart(3, '0')}`, ready: true }))
    .filter(f => (p.band == null || f.band === p.band) && (p.detector == null || f.detector === p.detector))
  if ('ra' in q) { r.query.ra = q.ra; r.query.dec = q.dec; r.query.target = null }
  r.complete = true
  r.pending = 0
  return delay(r)
}

export function imageUrl(frame: Frame, o: ImageOptions): string {
  if (o.layer === 'flags') return '' // los fixtures no traen máscara: '' = capa no disponible
  const i = (parseInt(frame.id.replace(/\D/g, ''), 10) || 0) % N_IMG
  return `${import.meta.env.BASE_URL}fixtures/img/fx-${String(i + 1).padStart(2, '0')}.png`
}

export function meta(frame: Frame): Promise<FrameMeta> {
  const m = structuredClone(metaFx) as unknown as FrameMeta
  return delay({ ...m, id: frame.id, mjd: frame.mjd, date: frame.date, detector: frame.detector,
    wavelength_um: frame.wavelength_um ?? m.wavelength_um, bandwidth_um: frame.bandwidth_um ?? m.bandwidth_um })
}

export const spectrum = () => delay(structuredClone(spectrumFx) as unknown as SpectrumResponse)

/** Curva sintética tipo Mira (~245 d) para que el panel tenga forma. Inventada. */
export function lightcurve(band: number): Promise<LightCurveResponse> {
  const mjds: number[] = [], flux: number[] = [], flux_err: number[] = []
  for (let k = 0; k < 34; k++) {
    const mjd = 60789 + k * 15.5
    mjds.push(mjd)
    flux.push(0.6 + 0.35 * Math.sin((2 * Math.PI * (mjd - 60789)) / 245) + band * 0.001)
    flux_err.push(0.03)
  }
  return delay({ mjds, flux, flux_err })
}

export function coverage(q: SkyQuery): Promise<CoverageResponse> {
  const r = baseFrames(q)
  const detectors: Partial<Record<Detector, number>> = {}
  const byDate = new Map<string, Set<Detector>>()
  for (const f of r.frames) {
    detectors[f.detector] = (detectors[f.detector] ?? 0) + 1
    const d = f.date.slice(0, 10)
    if (!byDate.has(d)) byDate.set(d, new Set())
    byDate.get(d)!.add(f.detector)
  }
  return delay({
    query: r.query, total: r.n_frames, detectors, collections: {},
    dates: [...byDate].map(([date, s]) => ({ date, count: s.size, detectors: [...s] })),
  })
}

export function diffCheck(a: Frame, b: Frame): Promise<ApiError | null> {
  if (a.detector !== b.detector)
    return delay(new ApiError(422, { error: 'not_comparable', detail: `distinto detector (${a.detector} vs ${b.detector})` }))
  return delay(null)
}
