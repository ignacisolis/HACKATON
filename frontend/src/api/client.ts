// Única capa de acceso a datos. Ningún componente hace fetch por su cuenta ni sabe si los datos
// vienen del backend real o de los fixtures (VITE_USE_FIXTURES=1).
import type {
  ApiErrorBody, CoverageResponse, Frame, FrameMeta, FramesResponse, ImageOptions,
  LightCurveResponse, SkyQuery, SpectrumResponse, TargetSummary, Detector,
} from './types'
import * as fx from './fixtures'

export const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === '1'
/** '' = mismo origen (en dev, Vite hace proxy de /api a localhost:8000) */
export const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  status: number
  code: string
  constructor(status: number, body: ApiErrorBody) {
    super(body.detail || body.error)
    this.status = status
    this.code = body.error
  }
}

function skyParams(q: SkyQuery): Record<string, string> {
  const p: Record<string, string> = {}
  if ('target' in q) p.target = q.target
  else { p.ra = String(q.ra); p.dec = String(q.dec) }
  if (q.size != null) p.size = String(q.size)
  return p
}

function url(path: string, params: Record<string, string | number | undefined | null> = {}): string {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v != null && v !== '') qs.set(k, String(v))
  const s = qs.toString()
  return `${API_BASE}${path}${s ? `?${s}` : ''}`
}

async function getJson<T>(u: string, signal?: AbortSignal): Promise<T> {
  let r: Response
  try {
    r = await fetch(u, { signal })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new ApiError(0, { error: 'network', detail: `No se pudo contactar al backend (${API_BASE || 'mismo origen'})` })
  }
  if (!r.ok) {
    let body: ApiErrorBody = { error: 'http_' + r.status, detail: r.statusText }
    try { body = await r.json() } catch { /* el backend siempre manda JSON, pero por si acaso */ }
    throw new ApiError(r.status, body)
  }
  return r.json() as Promise<T>
}

export interface FramesParams {
  band?: number | null
  detector?: Detector | null
  limit?: number
  offset?: number
}

export const api = {
  targets: async (signal?: AbortSignal): Promise<TargetSummary[]> =>
    USE_FIXTURES ? fx.targets() : (await getJson<{ targets: TargetSummary[] }>(url('/api/targets'), signal)).targets,

  frames: (q: SkyQuery, p: FramesParams = {}, signal?: AbortSignal): Promise<FramesResponse> =>
    USE_FIXTURES ? fx.frames(q, p)
      : getJson(url('/api/frames', { ...skyParams(q), band: p.band, detector: p.detector, limit: p.limit, offset: p.offset }), signal),

  coverage: (q: SkyQuery, signal?: AbortSignal): Promise<CoverageResponse> =>
    USE_FIXTURES ? fx.coverage(q) : getJson(url('/api/coverage', skyParams(q)), signal),

  meta: (frame: Frame, q: SkyQuery, signal?: AbortSignal): Promise<FrameMeta> =>
    USE_FIXTURES ? fx.meta(frame) : getJson(url(`/api/frame/${encodeURIComponent(frame.id)}/meta`, skyParams(q)), signal),

  spectrum: (q: SkyQuery, signal?: AbortSignal): Promise<SpectrumResponse> =>
    USE_FIXTURES ? fx.spectrum() : getJson(url('/api/spectrum', skyParams(q)), signal),

  lightcurve: (q: SkyQuery, band: number, signal?: AbortSignal): Promise<LightCurveResponse> =>
    USE_FIXTURES ? fx.lightcurve(band) : getJson(url('/api/lightcurve', { ...skyParams(q), band }), signal),

  /** URL del PNG de un cuadro (norte arriba, grilla de cielo fija). Va directo a un <img>. */
  frameImageUrl(frame: Frame, q: SkyQuery, o: ImageOptions = {}): string {
    if (USE_FIXTURES) return fx.imageUrl(frame, o)
    return url(`/api/frame/${encodeURIComponent(frame.id)}/png`, {
      ...skyParams(q),
      layer: o.layer && o.layer !== 'image' ? o.layer : undefined,
      stretch: o.stretch ?? 'asinh',
      vmin: o.vmin, vmax: o.vmax,
      bits: o.bits?.length ? o.bits.join(',') : undefined,
    })
  },

  /**
   * URL del recorte FITS original de un cuadro: el MEF tal como lo sirve IRSA.
   * El backend responde 302 al cutout. Devuelve null con fixtures, donde no hay backend.
   */
  frameFitsUrl(frame: Frame, q: SkyQuery): string | null {
    if (USE_FIXTURES) return null
    return url(`/api/frame/${encodeURIComponent(frame.id)}/fits`, skyParams(q))
  },

  /**
   * Resta a − b como PNG. PROPUESTA de contrato (pendiente con Camilo): GET /api/diff?a=&b=&…
   * Responde 422 {error, detail} si no son comparables (core.is_comparable). Hasta que exista,
   * el backend devuelve 404: usar diffCheck() para mostrar el motivo.
   */
  diffImageUrl(a: Frame, b: Frame, q: SkyQuery, o: Pick<ImageOptions, 'vmin' | 'vmax'> = {}): string {
    if (USE_FIXTURES) return fx.imageUrl(a, {})
    return url('/api/diff', { ...skyParams(q), a: a.id, b: b.id, vmin: o.vmin, vmax: o.vmax })
  },

  /** Pide la resta y devuelve null si salió bien o el error (422 = no comparables, 404 = endpoint aún no existe). */
  async diffCheck(a: Frame, b: Frame, q: SkyQuery, signal?: AbortSignal): Promise<ApiError | null> {
    if (USE_FIXTURES) return fx.diffCheck(a, b)
    try {
      const r = await fetch(this.diffImageUrl(a, b, q), { signal })
      if (r.ok) return null
      let body: ApiErrorBody = { error: 'http_' + r.status, detail: r.statusText }
      try { body = await r.json() } catch { /* */ }
      return new ApiError(r.status, body)
    } catch (e) {
      if ((e as Error).name === 'AbortError') throw e
      return new ApiError(0, { error: 'network', detail: String(e) })
    }
  },
}
