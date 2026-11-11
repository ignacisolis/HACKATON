// Metadata del cuadro actual, cacheada por (id, consulta) para no repedirla cuando el reproductor
// vuelve sobre un cuadro. Al cambiar de cuadro se aborta el pedido anterior y, mientras llega el
// nuevo, se sigue mostrando la última metadata recibida marcada como desactualizada (evita parpadeo
// al reproducir).
import { useEffect, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { Frame, FrameMeta, SkyQuery } from '../../api/types'

const MAX_CACHE = 300
const cache = new Map<string, FrameMeta>()
/** Pequeña espera antes de pedir: si el video pasa de largo, no se pide cada cuadro. */
const DEBOUNCE_MS = 120

export const metaKey = (frameId: string, q: SkyQuery) => `${frameId}|${JSON.stringify(q)}`

function remember(key: string, m: FrameMeta) {
  cache.set(key, m)
  if (cache.size > MAX_CACHE) cache.delete(cache.keys().next().value!)
}

export interface FrameMetaState {
  meta: FrameMeta | null
  /** true si `meta` es de otro cuadro (el del cuadro actual todavía no llegó) */
  stale: boolean
  loading: boolean
  /** el cuadro todavía se está bajando de IRSA (ready=false) */
  notReady: boolean
  error: ApiError | null
  retry: () => void
}

interface Last { key: string; meta: FrameMeta | null; error: ApiError | null }

/** `frame` null = no pedir nada (p. ej. la pestaña activa no usa metadata). */
export function useFrameMeta(frame: Frame | null, query: SkyQuery | null): FrameMetaState {
  const key = frame && query ? metaKey(frame.id, query) : null
  const notReady = frame?.ready === false
  const [nonce, setNonce] = useState(0)
  const [last, setLast] = useState<Last | null>(null)
  const hit = key ? cache.get(key) : undefined

  useEffect(() => {
    if (!key || !frame || !query || notReady || cache.has(key)) return
    const ac = new AbortController()
    const timer = window.setTimeout(() => {
      api.meta(frame, query, ac.signal).then(m => {
        remember(key, m)
        setLast({ key, meta: m, error: null })
      }).catch(e => {
        if ((e as Error).name === 'AbortError') return
        const err = e instanceof ApiError ? e : new ApiError(0, { error: 'unknown', detail: String(e) })
        setLast(p => ({ key, meta: p?.meta ?? null, error: err }))
      })
    }, DEBOUNCE_MS)
    return () => { window.clearTimeout(timer); ac.abort() }
  }, [key, notReady, nonce]) // eslint-disable-line react-hooks/exhaustive-deps

  const error = key && last?.key === key ? last.error : null
  const meta = key ? hit ?? last?.meta ?? null : null
  return {
    meta,
    stale: meta != null && !hit,
    loading: key != null && !hit && !notReady && !error,
    notReady,
    error,
    retry: () => { setLast(p => (p ? { ...p, key: '', error: null } : p)); setNonce(n => n + 1) },
  }
}
