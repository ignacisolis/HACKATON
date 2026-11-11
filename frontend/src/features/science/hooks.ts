// Hooks chicos del panel de ciencia: un fetch cancelable con reintento y el ancho de un contenedor.
import {
  useCallback, useEffect, useRef, useState,
  type KeyboardEvent, type MouseEvent, type PointerEvent, type RefObject,
} from 'react'
import { nearestIndex } from './chart'

export type Status = 'idle' | 'loading' | 'ok' | 'error'
export interface Resource<T> { status: Status; data: T | null; error: unknown; reload: () => void }

/** Pide `fetcher` cada vez que cambia `key` (null = no pedir nada). Cancela el pedido anterior.
 *  El estado "cargando" se deriva (no hay setState sincrónico en el efecto): mientras la respuesta
 *  guardada no sea la del pedido actual, está cargando. */
export function useResource<T>(key: string | null, fetcher: (signal: AbortSignal) => Promise<T>): Resource<T> {
  const [nonce, setNonce] = useState(0)
  const req = key == null ? null : `${nonce}|${key}`
  const [settled, setSettled] = useState<{ req: string; status: 'ok' | 'error'; data: T | null; error: unknown } | null>(null)
  const fetcherRef = useRef(fetcher)
  useEffect(() => { fetcherRef.current = fetcher })

  useEffect(() => {
    if (req == null) return
    const ac = new AbortController()
    fetcherRef.current(ac.signal).then(
      data => { if (!ac.signal.aborted) setSettled({ req, status: 'ok', data, error: null }) },
      error => {
        if (!ac.signal.aborted && (error as Error)?.name !== 'AbortError') setSettled({ req, status: 'error', data: null, error })
      },
    )
    return () => ac.abort()
  }, [req])

  const reload = useCallback(() => setNonce(n => n + 1), [])
  const cur = settled && settled.req === req ? settled : null
  const status: Status = req == null ? 'idle' : cur ? cur.status : 'loading'
  return { status, data: cur?.data ?? null, error: cur?.error ?? null, reload }
}

/** Cursor de un gráfico de puntos: hover/tacto eligen el punto más cercano; con el teclado,
 *  ← → Inicio Fin recorren los puntos y Enter/Espacio confirma. `onPick` es opcional. */
export function useChartCursor(pos: { x: number; y: number }[], o: {
  maxDist: number; start?: number; onPick?: (i: number) => void
}) {
  const [rawActive, setActive] = useState<number | null>(null)
  const n = pos.length
  const active = rawActive != null && rawActive < n ? rawActive : null

  const nearest = (e: PointerEvent<SVGSVGElement> | MouseEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    return nearestIndex(pos, e.clientX - r.left, e.clientY - r.top, o.maxDist)
  }
  const handlers = {
    onPointerMove: (e: PointerEvent<SVGSVGElement>) => { const i = nearest(e); setActive(i < 0 ? null : i) },
    onPointerLeave: () => setActive(null),
    onClick: (e: MouseEvent<SVGSVGElement>) => {
      const i = nearest(e)
      if (i >= 0) { setActive(i); o.onPick?.(i) }
    },
    onFocus: () => setActive(active ?? (n ? Math.min(o.start ?? 0, n - 1) : null)),
    onBlur: () => setActive(null),
    onKeyDown: (e: KeyboardEvent<SVGSVGElement>) => {
      if (!n) return
      const cur = active ?? Math.min(o.start ?? 0, n - 1)
      let next: number | null = null
      if (e.key === 'ArrowRight' || e.key === 'ArrowUp') next = Math.min(n - 1, cur + (active == null ? 0 : 1))
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') next = Math.max(0, cur - (active == null ? 0 : 1))
      else if (e.key === 'Home') next = 0
      else if (e.key === 'End') next = n - 1
      else if ((e.key === 'Enter' || e.key === ' ') && o.onPick) { e.preventDefault(); o.onPick(cur); return }
      if (next != null) { e.preventDefault(); setActive(next) }
    },
  }
  return { active, handlers }
}

/** Ancho en px de un elemento, con ResizeObserver (avisa apenas observa). Sin RO (jsdom) queda el fallback. */
export function useWidth(ref: RefObject<HTMLElement | null>, fallback = 600): number {
  const [w, setW] = useState(fallback)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(entries => {
      const cw = Math.floor(entries[0]?.contentRect.width ?? 0)
      if (cw > 0) setW(cw)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [ref])
  return w
}
