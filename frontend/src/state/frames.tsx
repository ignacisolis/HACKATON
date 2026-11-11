// Cuadros de la vista actual, compartidos por el reproductor, el panel de metadata, las máscaras y
// la resta. Un solo fetch por vista; se re-pide cada 2.5 s mientras el backend siga bajando de IRSA
// (carga progresiva: ready=false hasta que el cuadro está en caché).
import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, ApiError } from '../api/client'
import type { CoverageResponse, Detector, Frame, FramesResponse, SkyQuery } from '../api/types'
import { buildSequence } from '../features/player/sequence'
import { skyQueryOf, useView } from './view'

interface FramesCtx {
  query: SkyQuery | null
  coverage: CoverageResponse | null
  /** detector efectivo: el de la URL o, si no hay, el de más fechas según /api/coverage */
  detector: Detector | null
  response: FramesResponse | null
  /** todos los cuadros devueltos para ese detector (y banda, si está fija), por mjd */
  frames: Frame[]
  /** lo que reproduce el video (ver features/player/sequence.ts) */
  sequence: Frame[]
  /** sequence[t] acotado */
  current: Frame | null
  loading: boolean
  error: ApiError | null
  reload: () => void
}

const Ctx = createContext<FramesCtx | null>(null)
const POLL_MS = 2500

/** Detector con más fechas distintas: el video más largo posible sin mezclar detectores. */
export function bestDetector(c: CoverageResponse): Detector | null {
  const n = new Map<Detector, number>()
  for (const d of c.dates) for (const det of d.detectors) n.set(det, (n.get(det) ?? 0) + 1)
  let best: Detector | null = null
  for (const [det, k] of n) if (best == null || k > n.get(best)!) best = det
  return best
}

export function FramesProvider({ children }: { children: ReactNode }) {
  const { view } = useView()
  const query = useMemo(() => skyQueryOf(view), [view.target, view.ra, view.dec, view.fov]) // eslint-disable-line react-hooks/exhaustive-deps
  const qKey = JSON.stringify(query)
  const [coverage, setCoverage] = useState<CoverageResponse | null>(null)
  const [response, setResponse] = useState<FramesResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [nonce, setNonce] = useState(0)
  const timer = useRef<number | undefined>(undefined)

  // 1) cobertura: barata (no baja cutouts) y sirve para elegir el detector por defecto
  useEffect(() => {
    setCoverage(null)
    if (!query) return
    const ac = new AbortController()
    api.coverage(query, ac.signal).then(setCoverage).catch(e => {
      if (e.name !== 'AbortError') setError(e instanceof ApiError ? e : new ApiError(0, { error: 'unknown', detail: String(e) }))
    })
    return () => ac.abort()
  }, [qKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const detector: Detector | null = view.det ?? (coverage ? bestDetector(coverage) : null)

  // 2) cuadros de ese detector, con re-pedido mientras el backend no termine
  useEffect(() => {
    setResponse(null); setError(null)
    if (!query || !detector) return
    const ac = new AbortController()
    let stopped = false
    const tick = async (first: boolean) => {
      if (first) setLoading(true)
      try {
        const r = await api.frames(query, { detector, band: view.band }, ac.signal)
        if (stopped) return
        setResponse(r); setError(null)
        if (r.complete === false) timer.current = window.setTimeout(() => tick(false), POLL_MS)
      } catch (e) {
        if ((e as Error).name === 'AbortError' || stopped) return
        setError(e instanceof ApiError ? e : new ApiError(0, { error: 'unknown', detail: String(e) }))
      } finally {
        if (first && !stopped) setLoading(false)
      }
    }
    tick(true)
    return () => { stopped = true; ac.abort(); window.clearTimeout(timer.current) }
  }, [qKey, detector, view.band, nonce]) // eslint-disable-line react-hooks/exhaustive-deps

  const frames = useMemo(() => response?.frames ?? [], [response])
  const sequence = useMemo(() => buildSequence(frames, { band: view.band }), [frames, view.band])
  const current = sequence.length ? sequence[Math.min(view.t, sequence.length - 1)] : null

  const value: FramesCtx = {
    query, coverage, detector, response, frames, sequence, current, loading, error,
    reload: () => setNonce(n => n + 1),
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useFrames(): FramesCtx {
  const c = useContext(Ctx)
  if (!c) throw new Error('useFrames fuera de <FramesProvider>')
  return c
}
