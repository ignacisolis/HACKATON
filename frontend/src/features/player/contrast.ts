// Contraste común para todo el video (decisión 11 del contrato, propuesta del 11/11).
//
// Sin esto cada PNG se estira con su propio ZScale: un cuadro donde la estrella está 7 veces más
// brillante se oscurece solo para compensar, y el video de una variable (RW Aur) parece quieto.
// Con un vmin/vmax común, el brillo que cambia entre cuadros es el del cielo, no el del estirado.
//
// Cómo se arma (por secuencia, que ya es de un solo detector):
//   vmin = mediana de los mínimos de ZScale  → el fondo típico queda negro en todos los cuadros
//   vmax = percentil 90 de los máximos       → el cuadro más brillante no se quema entero; un
//          cuadro raro (saturado, rayo cósmico) no oscurece todo el resto
// Con asinh el máximo de cada cuadro es max(zscale_hi, p99.7), igual que hace el backend
// (render.stretch) para no quemar las fuentes brillantes.
import type { Frame, Stretch } from '../../api/types'

export interface Range { vmin: number; vmax: number }

function quantile(xs: number[], q: number): number {
  const s = [...xs].sort((a, b) => a - b)
  const pos = (s.length - 1) * q
  const lo = Math.floor(pos), hi = Math.ceil(pos)
  return s[lo] + (s[hi] - s[lo]) * (pos - lo)
}

/** 3 cifras significativas: que la URL no cambie por ruido cuando llega un cuadro más. */
export const round3 = (x: number) => (x === 0 ? 0 : Number(x.toPrecision(3)))

/**
 * Rango común para estirar todos los cuadros de la secuencia, o null si no se puede (sin
 * display_range: fixtures, backend viejo, o menos de 2 cuadros con datos).
 */
export function commonRange(seq: Frame[], stretch: Stretch): Range | null {
  const lo: number[] = [], hi: number[] = []
  for (const f of seq) {
    const d = f.display_range
    if (!d || !Array.isArray(d.zscale)) continue
    const [z0, z1] = d.zscale
    if (!Number.isFinite(z0) || !Number.isFinite(z1)) continue
    lo.push(z0)
    hi.push(stretch === 'asinh' && Number.isFinite(d.p99_7) ? Math.max(z1, d.p99_7) : z1)
  }
  if (lo.length < 2) return null
  const vmin = round3(quantile(lo, 0.5))
  const vmax = round3(quantile(hi, 0.9))
  return vmax > vmin ? { vmin, vmax } : null
}
