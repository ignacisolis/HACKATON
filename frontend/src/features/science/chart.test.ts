import { describe, expect, it } from 'vitest'
import {
  dateToMjd, extentWithErrors, formatNum, linearScale, logScale, logTicks, monthTicks,
  nearestIndex, niceLinearTicks, stackLabels,
} from './chart'
import { mjdToDate } from '../../lib/sky'

describe('escalas', () => {
  it('lineal mapea extremos e invierte', () => {
    const s = linearScale([0, 10], [100, 200])
    expect(s(0)).toBe(100)
    expect(s(5)).toBe(150)
    expect(s.invert(175)).toBeCloseTo(7.5)
  })
  it('lineal con eje invertido (y hacia abajo)', () => {
    const s = linearScale([0, 1], [300, 20])
    expect(s(1)).toBe(20)
    expect(s.invert(300)).toBe(0)
  })
  it('log reparte décadas en partes iguales', () => {
    const s = logScale([0.1, 10], [0, 200])
    expect(s(1)).toBeCloseTo(100)
    expect(s(10)).toBeCloseTo(200)
    expect(s.invert(100)).toBeCloseTo(1)
    expect(s(0)).toBeNaN()
    expect(s(-1)).toBeNaN()
  })
  it('log rechaza dominios no positivos', () => {
    expect(() => logScale([0, 1], [0, 1])).toThrow()
  })
  it('el eje de λ de SPHEREx: 1 µm queda más cerca de 0.7 que de 5.1', () => {
    const s = logScale([0.7, 5.1], [0, 1000])
    expect(s(1)).toBeGreaterThan(150)
    expect(s(1)).toBeLessThan(200)
  })
})

describe('ticks', () => {
  it('lineales lindos', () => {
    expect(niceLinearTicks(0, 1, 6)).toEqual([0, 0.2, 0.4, 0.6, 0.8, 1])
    expect(niceLinearTicks(0.13, 0.91, 5)).toEqual([0.2, 0.4, 0.6, 0.8])
    expect(niceLinearTicks(-3, 3, 4)).toEqual([-2, 0, 2])
    expect(niceLinearTicks(2, 2)).toEqual([2])
  })
  it('lineales no pasan de maxTicks', () => {
    for (const [a, b] of [[0, 7], [0.001, 0.0093], [-120, 4500], [3, 3.2]]) {
      const t = niceLinearTicks(a, b, 5)
      expect(t.length).toBeLessThanOrEqual(5)
      expect(t.length).toBeGreaterThanOrEqual(2)
      for (const v of t) { expect(v).toBeGreaterThanOrEqual(a - 1e-9); expect(v).toBeLessThanOrEqual(b + 1e-9) }
    }
  })
  it('log en el rango de λ: denso si hay lugar, ralo si no', () => {
    expect(logTicks(0.7, 5.1, 8)).toEqual([0.7, 0.8, 0.9, 1, 2, 3, 4, 5])
    expect(logTicks(0.7, 5.1, 6)).toEqual([0.7, 1, 2, 3, 4, 5])
    expect(logTicks(0.7, 5.1, 4)).toEqual([1, 2, 3, 5])
  })
  it('log cae a lineal si el rango es muy corto', () => {
    const t = logTicks(0.42, 0.48, 6)
    expect(t.length).toBeGreaterThanOrEqual(2)
    expect(t.every(v => v >= 0.42 && v <= 0.48)).toBe(true)
  })
  it('log ignora dominios no positivos', () => {
    expect(logTicks(0, 1)).toEqual([])
  })
})

describe('formatNum', () => {
  it('corto y sin ceros de más', () => {
    expect(formatNum(0.34210)).toBe('0.342')
    expect(formatNum(2)).toBe('2')
    expect(formatNum(0)).toBe('0')
    expect(formatNum(NaN)).toBe('—')
    expect(formatNum(1.5e-5)).toContain('×10^')
  })
})

describe('extentWithErrors', () => {
  const rows = [{ v: 1, err: 0.1 }, { v: 3, err: 0.5 }, { v: -0.2, err: 0.1 }]
  it('lineal incluye las barras de error', () => {
    const [lo, hi] = extentWithErrors(rows, 'linear', 0)!
    expect(lo).toBeCloseTo(-0.3)
    expect(hi).toBeCloseTo(3.5)
  })
  it('log ignora flujos ≤ 0 y errores que cruzan el cero', () => {
    const [lo, hi] = extentWithErrors([...rows, { v: 0.05, err: 0.2 }], 'log', 0)!
    expect(lo).toBeCloseTo(0.05)
    expect(hi).toBeCloseTo(3.5)
  })
  it('sin datos válidos devuelve null; un solo valor abre un margen', () => {
    expect(extentWithErrors([], 'linear')).toBeNull()
    expect(extentWithErrors([{ v: -1, err: 0 }], 'log')).toBeNull()
    const [lo, hi] = extentWithErrors([{ v: 2, err: 0 }], 'linear')!
    expect(lo).toBeLessThan(2); expect(hi).toBeGreaterThan(2)
  })
})

describe('fechas', () => {
  it('dateToMjd es la inversa de mjdToDate', () => {
    expect(dateToMjd(mjdToDate(60834.788416907))).toBeCloseTo(60834.788416907, 6)
    expect(dateToMjd(new Date(Date.UTC(1970, 0, 1)))).toBe(40587)
  })
  it('ticks mensuales caen el día 1 y respetan maxTicks', () => {
    // cobertura de R Dra: 2025-04-24 → 2026-09-27 (~522 días)
    const a = dateToMjd(new Date(Date.UTC(2025, 3, 24))), b = dateToMjd(new Date(Date.UTC(2026, 8, 27)))
    const t = monthTicks(a, b, 6)
    expect(t.length).toBeGreaterThanOrEqual(3)
    expect(t.length).toBeLessThanOrEqual(6)
    for (const m of t) {
      const d = mjdToDate(m)
      expect(d.getUTCDate()).toBe(1)
      expect(m).toBeGreaterThanOrEqual(a); expect(m).toBeLessThanOrEqual(b)
    }
    expect(mjdToDate(t[0]).getUTCMonth() % 3).toBe(0) // paso trimestral: ene, abr, jul, oct
  })
  it('rango corto da ticks mensuales', () => {
    const a = dateToMjd(new Date(Date.UTC(2025, 0, 10))), b = dateToMjd(new Date(Date.UTC(2025, 3, 20)))
    expect(monthTicks(a, b, 6).map(m => mjdToDate(m).getUTCMonth())).toEqual([1, 2, 3])
  })
})

describe('stackLabels', () => {
  it('etiquetas cercanas suben de fila; lejanas vuelven a la primera', () => {
    expect(stackLabels([0, 10, 50, 55, 200], 30)).toEqual([0, 1, 0, 1, 0])
  })
  it('respeta el orden de entrada aunque no venga ordenado', () => {
    expect(stackLabels([50, 0, 10], 30)).toEqual([0, 0, 1])
  })
  it('acepta un ancho por etiqueta', () => {
    // la primera es larga (80 px): la de x=50 no entra en su fila; la de x=90 sí
    expect(stackLabels([0, 50, 90], [80, 20, 20])).toEqual([0, 1, 0])
  })
})

describe('nearestIndex', () => {
  const pts = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 50 }]
  it('elige el más cercano en 2D', () => {
    expect(nearestIndex(pts, 9, 40)).toBe(2)
    expect(nearestIndex(pts, 2, 1)).toBe(0)
  })
  it('respeta la distancia máxima', () => {
    expect(nearestIndex(pts, 100, 100, 20)).toBe(-1)
  })
})
