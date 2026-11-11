// Lógica pura de reproducción y formato. Testeada en playback.test.ts.
import type { LoadStatus } from './preload'

/** Próximo cuadro a mostrar al reproducir: el siguiente ya cargado (en bucle). Si el siguiente
 *  todavía no llegó, se queda en `i` (espera, no saltea: el orden temporal importa). Los que
 *  fallaron se saltean. */
export function nextPlayable(i: number, n: number, st: (k: number) => LoadStatus | undefined): number {
  if (n < 2) return i
  for (let s = 1; s < n; s++) {
    const k = (i + s) % n
    const x = st(k)
    if (x === 'loaded') return k
    if (x === 'error') continue
    return i
  }
  return i
}

/** '2025-06-08T18:55:19.221' → '2025-06-08 18:55 UTC' (sin pasar por la zona horaria local). */
export function formatDateUTC(iso: string): string {
  if (!iso) return ''
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`
}

/** λ ± Δλ/2 en µm. */
export function formatWavelength(wl: number | null, bw: number | null): string {
  if (wl == null) return '—'
  return bw != null ? `${wl.toFixed(3)} ± ${(bw / 2).toFixed(3)} µm` : `${wl.toFixed(3)} µm`
}

/** Acota un índice a la secuencia. */
export const clampIndex = (t: number, n: number) => (n <= 0 ? 0 : Math.max(0, Math.min(Math.floor(t), n - 1)))

export const SPEEDS = [1, 2, 4, 8, 12] as const
