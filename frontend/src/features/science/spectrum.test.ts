import { describe, expect, it } from 'vitest'
import spectrumFx from '../../../../contracts/fixtures/spectrum.json'
import { ApiError } from '../../api/client'
import type { SpectrumPoint, SpectrumResponse } from '../../api/types'
import {
  MOLECULAR_REFS, WL_DOMAIN, classifyError, detectorRanges, fluxDomain, isSelected, lightCurveRows, plottable,
} from './spectrum'

const fx = spectrumFx as unknown as SpectrumResponse
const pt = (o: Partial<SpectrumPoint>): SpectrumPoint => ({
  wavelength_um: 1.5, bandwidth_um: 0.04, band: 20, flux: 1, flux_err: 0.1, unit: 'MJy/sr',
  detector: 'D2', n_epochs: 3, flagged_fraction: 0, quality: 'ok', ...o,
})

describe('fixture de espectro', () => {
  it('todos los puntos caen dentro del eje de λ', () => {
    for (const p of fx.points) {
      expect(p.wavelength_um - p.bandwidth_um / 2).toBeGreaterThan(WL_DOMAIN[0])
      expect(p.wavelength_um + p.bandwidth_um / 2).toBeLessThan(WL_DOMAIN[1])
    }
  })
  it('los 6 detectores aparecen en orden de λ', () => {
    const r = detectorRanges(fx.points)
    expect(r.map(x => x.detector)).toEqual(['D1', 'D2', 'D3', 'D4', 'D5', 'D6'])
    for (let i = 1; i < r.length; i++) expect(r[i].min).toBeGreaterThan(r[i - 1].min)
  })
  it('las bandas de D5–D6 son más angostas relativamente (R más alta)', () => {
    const rel = (d: string) => {
      const ps = fx.points.filter(p => p.detector === d)
      return ps.reduce((s, p) => s + p.bandwidth_um / p.wavelength_um, 0) / ps.length
    }
    expect(rel('D6')).toBeLessThan(rel('D1') / 2)
  })
})

describe('plottable', () => {
  const pts = [pt({ quality: 'bad', wavelength_um: 2 }), pt({ flux: -0.1, wavelength_um: 3 }), pt({ wavelength_um: 1 }), pt({ flux: NaN })]
  it('oculta los malos salvo que se pidan, y ordena por λ', () => {
    const r = plottable(pts, { showBad: false, scale: 'linear' })
    expect(r.hiddenBad).toBe(1)
    expect(r.shown.map(p => p.wavelength_um)).toEqual([1, 3])
    expect(plottable(pts, { showBad: true, scale: 'linear' }).shown).toHaveLength(3)
  })
  it('en log saca los flujos ≤ 0 y los cuenta', () => {
    const r = plottable(pts, { showBad: true, scale: 'log' })
    expect(r.hiddenNonPositive).toBe(1)
    expect(r.shown.every(p => p.flux > 0)).toBe(true)
  })
})

describe('fluxDomain', () => {
  it('incluye las barras de error', () => {
    const [lo, hi] = fluxDomain([pt({ flux: 1, flux_err: 0.5 }), pt({ flux: 2, flux_err: 0.5 })], 'linear')!
    expect(lo).toBeLessThan(0.5)
    expect(hi).toBeGreaterThan(2.5)
  })
})

describe('isSelected', () => {
  it('compara banda y, si hay, detector', () => {
    const p = pt({ band: 24, detector: 'D2' })
    expect(isSelected(p, 24, 'D2')).toBe(true)
    expect(isSelected(p, 24, null)).toBe(true)
    expect(isSelected(p, 24, 'D3')).toBe(false)
    expect(isSelected(p, null, 'D2')).toBe(false)
  })
})

describe('referencias moleculares', () => {
  it('están dentro del rango de SPHEREx y ordenadas', () => {
    for (const r of MOLECULAR_REFS) { expect(r.um).toBeGreaterThan(WL_DOMAIN[0]); expect(r.um).toBeLessThan(WL_DOMAIN[1]) }
    const um = MOLECULAR_REFS.map(r => r.um)
    expect([...um].sort((a, b) => a - b)).toEqual(um)
    expect(new Set(MOLECULAR_REFS.map(r => r.id)).size).toBe(MOLECULAR_REFS.length)
  })
})

describe('lightCurveRows', () => {
  it('ordena por fecha, descarta no finitos y tolera arrays desparejos', () => {
    const rows = lightCurveRows({ mjds: [3, 1, 2, 4], flux: [30, 10, NaN, 40], flux_err: [1, 1, 1] })
    expect(rows).toEqual([{ mjd: 1, flux: 10, err: 1 }, { mjd: 3, flux: 30, err: 1 }, { mjd: 4, flux: 40, err: 0 }])
  })
})

describe('classifyError', () => {
  it('501 es "todavía no implementado", no un error', () => {
    expect(classifyError(new ApiError(501, { error: 'not_implemented', detail: '' }))).toBe('not_implemented')
    expect(classifyError(new ApiError(500, { error: 'not_implemented', detail: '' }))).toBe('not_implemented')
    expect(classifyError(new ApiError(0, { error: 'network', detail: '' }))).toBe('network')
    expect(classifyError(new ApiError(500, { error: 'boom', detail: '' }))).toBe('error')
    expect(classifyError(new Error('x'))).toBe('error')
  })
})
