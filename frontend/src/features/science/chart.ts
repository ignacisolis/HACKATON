// Utilidades de gráfico, puras y sin dependencias (chart.test.ts). Los gráficos del panel de ciencia
// se dibujan a mano en SVG: acá viven las escalas, los ticks y el hit-testing.

export interface Scale {
  (v: number): number
  domain: [number, number]
  range: [number, number]
  invert: (px: number) => number
}

export function linearScale(domain: [number, number], range: [number, number]): Scale {
  const [d0, d1] = domain, [r0, r1] = range
  const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0)
  const s = ((v: number) => r0 + (v - d0) * k) as Scale
  s.domain = domain
  s.range = range
  s.invert = (px: number) => (k === 0 ? d0 : d0 + (px - r0) / k)
  return s
}

/** Escala logarítmica (base 10). El dominio tiene que ser > 0; valores ≤ 0 devuelven NaN. */
export function logScale(domain: [number, number], range: [number, number]): Scale {
  if (!(domain[0] > 0 && domain[1] > 0)) throw new Error('logScale: el dominio tiene que ser positivo')
  const lin = linearScale([Math.log10(domain[0]), Math.log10(domain[1])], range)
  const s = ((v: number) => (v > 0 ? lin(Math.log10(v)) : NaN)) as Scale
  s.domain = domain
  s.range = range
  s.invert = (px: number) => 10 ** lin.invert(px)
  return s
}

/** Redondeo para que 0.1 + 0.2 no se muestre como 0.30000000000000004. */
const clean = (v: number) => Number(v.toPrecision(12))

/** Ticks "lindos" (1, 2, 2.5, 5 × 10^k) para un eje lineal, como mucho ~maxTicks. */
export function niceLinearTicks(min: number, max: number, maxTicks = 5): number[] {
  if (!isFinite(min) || !isFinite(max)) return []
  if (min === max) return [clean(min)]
  if (min > max) [min, max] = [max, min]
  const raw = (max - min) / Math.max(1, maxTicks - 1)
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => (max - min) / s <= maxTicks - 1 + 1e-9) ?? 10 * mag
  const out: number[] = []
  for (let v = Math.ceil(min / step - 1e-9) * step; v <= max + step * 1e-9; v += step) out.push(clean(v))
  return out
}

const MANTISSAS = [[1], [1, 2, 5], [1, 2, 3, 5], [1, 2, 3, 4, 5, 7], [1, 2, 3, 4, 5, 6, 7, 8, 9]]

/** Ticks para un eje log: m × 10^k con el juego de mantisas más denso que no pase de maxTicks.
 *  Si el rango es tan chico que quedan menos de 2, cae a ticks lineales. */
export function logTicks(min: number, max: number, maxTicks = 8): number[] {
  if (!(min > 0 && max > 0)) return []
  if (min > max) [min, max] = [max, min]
  const k0 = Math.floor(Math.log10(min)), k1 = Math.ceil(Math.log10(max))
  let best: number[] = []
  for (const ms of MANTISSAS) {
    const ticks: number[] = []
    for (let k = k0; k <= k1; k++) for (const m of ms) {
      const v = clean(m * 10 ** k)
      if (v >= min * (1 - 1e-9) && v <= max * (1 + 1e-9)) ticks.push(v)
    }
    if (ticks.length <= maxTicks) best = ticks
    else break
  }
  return best.length >= 2 ? best : niceLinearTicks(min, max, Math.min(maxTicks, 5)).filter(v => v > 0)
}

/** Texto corto para un tick o un valor: sin ceros de más y con notación científica en los extremos. */
export function formatNum(v: number, digits = 3): string {
  if (!isFinite(v)) return '—'
  if (v === 0) return '0'
  const a = Math.abs(v)
  if (a >= 1e5 || a < 1e-3) return v.toExponential(Math.max(0, digits - 1)).replace('e', '×10^').replace('+', '')
  return String(Number(v.toPrecision(digits)))
}

/** Extensión [min, max] de valores con error, con un margen. En log solo cuentan los positivos;
 *  si la barra de error baja de 0, se usa el valor central para no estirar el eje a −∞. */
export function extentWithErrors(rows: { v: number; err: number }[], mode: 'linear' | 'log', pad = 0.06): [number, number] | null {
  let lo = Infinity, hi = -Infinity
  for (const { v, err } of rows) {
    if (!isFinite(v)) continue
    const e = isFinite(err) && err > 0 ? err : 0
    if (mode === 'log') {
      if (v <= 0) continue
      lo = Math.min(lo, v - e > 0 ? v - e : v)
      hi = Math.max(hi, v + e)
    } else {
      lo = Math.min(lo, v - e)
      hi = Math.max(hi, v + e)
    }
  }
  if (!isFinite(lo) || !isFinite(hi)) return null
  if (mode === 'log') {
    if (lo === hi) return [lo / 1.5, hi * 1.5]
    const f = (hi / lo) ** pad
    return [lo / f, hi * f]
  }
  if (lo === hi) { const d = Math.abs(lo) * 0.1 || 1; return [lo - d, hi + d] }
  const d = (hi - lo) * pad
  return [lo - d, hi + d]
}

// ---- fechas (MJD) ----------------------------------------------------------------------------

export const MJD_UNIX_EPOCH = 40587
export const dateToMjd = (d: Date) => d.getTime() / 86400000 + MJD_UNIX_EPOCH
const mjdToMs = (mjd: number) => (mjd - MJD_UNIX_EPOCH) * 86400000

/** Ticks al primer día de cada mes (UTC), cada 1, 2, 3, 6 o 12 meses: el paso más corto que entra. */
export function monthTicks(mjdMin: number, mjdMax: number, maxTicks = 6): number[] {
  if (!isFinite(mjdMin) || !isFinite(mjdMax) || mjdMax < mjdMin) return []
  const a = new Date(mjdToMs(mjdMin)), b = new Date(mjdToMs(mjdMax))
  const m0 = a.getUTCFullYear() * 12 + a.getUTCMonth() + (a.getUTCDate() > 1 || a.getUTCHours() > 0 ? 1 : 0)
  const m1 = b.getUTCFullYear() * 12 + b.getUTCMonth()
  for (const step of [1, 2, 3, 6, 12, 24]) {
    const first = Math.ceil(m0 / step) * step
    const out: number[] = []
    for (let m = first; m <= m1; m += step) out.push(dateToMjd(new Date(Date.UTC(Math.floor(m / 12), m % 12, 1))))
    if (out.length <= maxTicks) return out
  }
  return []
}

// ---- etiquetas e interacción -----------------------------------------------------------------

/** Reparte etiquetas en filas para que no se pisen. Cada etiqueta empieza en xs[i] y ocupa
 *  widths[i] px (o el mismo ancho para todas); va a la primera fila donde la anterior ya terminó.
 *  Devuelve la fila de cada una, en el orden dado. */
export function stackLabels(xs: number[], widths: number | number[]): number[] {
  const w = (i: number) => (typeof widths === 'number' ? widths : widths[i] ?? 0)
  const order = xs.map((x, i) => [x, i] as const).sort((p, q) => p[0] - q[0])
  const endOfRow: number[] = []
  const rows = new Array<number>(xs.length)
  for (const [x, i] of order) {
    let r = 0
    while (endOfRow[r] != null && x < endOfRow[r]) r++
    endOfRow[r] = x + w(i)
    rows[i] = r
  }
  return rows
}

/** Índice del punto más cercano a (x, y) en píxeles, o -1 si ninguno está a ≤ maxDist. */
export function nearestIndex(pts: { x: number; y: number }[], x: number, y: number, maxDist = Infinity): number {
  let best = -1, bestD = maxDist * maxDist
  pts.forEach((p, i) => {
    if (!isFinite(p.x) || !isFinite(p.y)) return
    const d = (p.x - x) ** 2 + (p.y - y) ** 2
    if (d <= bestD) { bestD = d; best = i }
  })
  return best
}

export const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))
