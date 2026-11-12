// Precarga de PNG para que el video no parpadee: un objeto Image por URL, guardado a nivel de módulo
// (cambiar de estiramiento y volver no re-descarga) y un store externo para que React se entere.
import { useEffect, useSyncExternalStore } from 'react'

export type LoadStatus = 'loaded' | 'error'

const images = new Map<string, HTMLImageElement>()
const status = new Map<string, LoadStatus>()
const subs = new Set<() => void>()
let version = 0
let scheduled = false

// muchas imágenes terminan en el mismo cuadro de animación: se avisa una sola vez por frame
function notify() {
  if (scheduled) return
  scheduled = true
  const run = () => { scheduled = false; version++; subs.forEach(f => f()) }
  if (typeof requestAnimationFrame === 'function') requestAnimationFrame(run)
  else setTimeout(run, 16)
}

function subscribe(f: () => void) { subs.add(f); return () => { subs.delete(f) } }
const getVersion = () => version

export function preload(u: string) {
  if (!u || images.has(u)) return
  const img = new Image()
  img.decoding = 'async'
  img.onload = () => { status.set(u, 'loaded'); notify() }
  img.onerror = () => { status.set(u, 'error'); notify() }
  images.set(u, img)
  img.src = u
}

export const loadStatus = (u: string): LoadStatus | undefined => (u ? status.get(u) : 'loaded')

/** Olvida las URLs que fallaron, para reintentarlas (botón "reintentar"). */
export function forgetErrors() {
  for (const [u, s] of status) if (s === 'error') { status.delete(u); images.delete(u) }
  notify()
}

/** Precarga `urls` empezando por `start` (el cuadro visible) y re-renderiza cuando llegan.
 *  `epoch` fuerza a reintentar (después de forgetErrors()).
 *  Devuelve la versión del store: usarla como dependencia de lo que lea loadStatus(). */
export function usePreload(urls: string[], start: number, epoch = 0): number {
  const v = useSyncExternalStore(subscribe, getVersion, getVersion)
  const key = urls.join('\n')
  useEffect(() => {
    const n = urls.length
    for (let k = 0; k < n; k++) preload(urls[(start + k) % n])
  }, [key, epoch]) // eslint-disable-line react-hooks/exhaustive-deps
  return v
}
