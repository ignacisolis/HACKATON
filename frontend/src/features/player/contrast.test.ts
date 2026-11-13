import { describe, expect, it } from 'vitest'
import type { Frame } from '../../api/types'
import { commonRange, round3 } from './contrast'

const f = (z0: number, z1: number, p: number): Frame => ({
  id: `f${z0}${z1}${p}`, mjd: 0, date: '2025-01-01T00:00:00', detector: 'D2', wavelength_um: 1.5, bandwidth_um: 0.04,
  band: 30, release: 'r', image_url: '', target_xy: [29, 29], flagged_fraction: 0, quality: 'ok', ready: true,
  display_range: { zscale: [z0, z1], p99_7: p },
})

describe('contraste común', () => {
  it('vmin = mediana de los mínimos, vmax = p90 de los máximos (linear)', () => {
    const seq = [f(0.1, 1, 5), f(0.2, 2, 5), f(0.3, 3, 5), f(0.4, 4, 5), f(0.5, 10, 5)]
    const r = commonRange(seq, 'linear')!
    expect(r.vmin).toBe(0.3)
    expect(r.vmax).toBeCloseTo(7.6, 6) // p90 de [1,2,3,4,10]
  })
  it('con asinh usa max(zscale_hi, p99.7) como hace el backend', () => {
    const seq = [f(0.1, 1, 20), f(0.1, 1, 20), f(0.1, 1, 20)]
    expect(commonRange(seq, 'asinh')!.vmax).toBe(20)
    expect(commonRange(seq, 'linear')!.vmax).toBe(1)
  })
  it('un cuadro brillante no oscurece todo: el máximo absoluto no manda', () => {
    const seq = [...Array.from({ length: 9 }, () => f(0.1, 1, 1)), f(0.1, 500, 500)]
    expect(commonRange(seq, 'linear')!.vmax).toBeLessThan(500)
  })
  it('sin display_range (fixtures o backend viejo) no hay rango común', () => {
    const seq = [{ ...f(0.1, 1, 1), display_range: undefined }, { ...f(0.1, 1, 1), display_range: null }]
    expect(commonRange(seq, 'asinh')).toBeNull()
    expect(commonRange([f(0.1, 1, 1)], 'asinh')).toBeNull()
  })
  it('redondea a 3 cifras para que la URL sea estable', () => {
    expect(round3(0.123456)).toBe(0.123)
    expect(round3(14.09631)).toBe(14.1)
  })
})
