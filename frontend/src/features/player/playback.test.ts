import { describe, expect, it } from 'vitest'
import type { CoverageResponse } from '../../api/types'
import { detectorCoverage, NOMINAL_RANGE_UM } from './detectors'
import d from './i18n'
import { clampIndex, formatDateUTC, formatWavelength, nextPlayable } from './playback'
import type { LoadStatus } from './preload'

const st = (arr: (LoadStatus | undefined)[]) => (k: number) => arr[k]

describe('nextPlayable', () => {
  it('avanza al siguiente cargado y da la vuelta', () => {
    expect(nextPlayable(0, 3, st(['loaded', 'loaded', 'loaded']))).toBe(1)
    expect(nextPlayable(2, 3, st(['loaded', 'loaded', 'loaded']))).toBe(0)
  })
  it('espera (no saltea) si el siguiente todavía no cargó', () => {
    expect(nextPlayable(0, 3, st(['loaded', undefined, 'loaded']))).toBe(0)
  })
  it('saltea los que fallaron', () => {
    expect(nextPlayable(0, 4, st(['loaded', 'error', 'error', 'loaded']))).toBe(3)
    expect(nextPlayable(0, 3, st(['loaded', 'error', 'error']))).toBe(0)
  })
  it('con 0 o 1 cuadros no se mueve', () => {
    expect(nextPlayable(0, 1, st(['loaded']))).toBe(0)
    expect(nextPlayable(0, 0, st([]))).toBe(0)
  })
})

describe('formato', () => {
  it('fecha UTC sin pasar por la zona local', () => {
    expect(formatDateUTC('2025-06-08T18:55:19.221')).toBe('2025-06-08 18:55 UTC')
  })
  it('λ ± Δλ/2', () => {
    expect(formatWavelength(1.5143, 0.0366)).toBe('1.514 ± 0.018 µm')
    expect(formatWavelength(1.5143, null)).toBe('1.514 µm')
    expect(formatWavelength(null, null)).toBe('—')
  })
  it('clampIndex', () => {
    expect(clampIndex(5, 3)).toBe(2)
    expect(clampIndex(-1, 3)).toBe(0)
    expect(clampIndex(4, 0)).toBe(0)
  })
})

describe('detectores', () => {
  it('cuenta fechas y cuadros por detector desde /api/coverage', () => {
    const c: CoverageResponse = {
      query: { ra: 0, dec: 0, size: 0.1 }, total: 30, collections: {},
      detectors: { D1: 20, D4: 10 },
      dates: [
        { date: '2025-06-06', count: 12, detectors: ['D1', 'D4'] },
        { date: '2025-07-04', count: 3, detectors: ['D1'] },
      ],
    }
    expect(detectorCoverage(c, 'D1')).toEqual({ dates: 2, frames: 20 })
    expect(detectorCoverage(c, 'D2')).toEqual({ dates: 0, frames: 0 })
    expect(detectorCoverage(null, 'D1')).toBeNull()
  })
  it('los rangos nominales van en orden y casi sin hueco', () => {
    const r = Object.values(NOMINAL_RANGE_UM)
    for (let k = 1; k < r.length; k++) expect(Math.abs(r[k][0] - r[k - 1][1])).toBeLessThan(0.02)
  })
})

describe('i18n del reproductor', () => {
  it('todas las claves en inglés y en español, con prefijo player.', () => {
    expect(Object.keys(d.en).sort()).toEqual(Object.keys(d.es).sort())
    for (const k of Object.keys(d.en)) expect(k.startsWith('player.')).toBe(true)
  })
  it('los mismos {placeholders} en los dos idiomas', () => {
    const vars = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join()
    for (const k of Object.keys(d.en)) expect(vars(d.es[k]), k).toBe(vars(d.en[k]))
  })
})
