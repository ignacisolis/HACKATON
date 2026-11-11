import { describe, expect, it } from 'vitest'
import { formatDec, formatRA, pixelToSky, skyToPixel } from './sky'
import { parseView, serializeView, DEFAULT_VIEW } from '../state/view'
import { missingKeys } from '../i18n'

describe('sky', () => {
  it('el centro del PNG es el centro del recorte', () => {
    const p = pixelToSky(29, 29, 59, 59, 133.76, -7.24, 0.1)
    expect(p.ra).toBeCloseTo(133.76, 6)
    expect(p.dec).toBeCloseTo(-7.24, 6)
  })
  it('este a la izquierda, norte arriba', () => {
    const left = pixelToSky(0, 29, 59, 59, 100, 0, 0.1)
    const up = pixelToSky(29, 0, 59, 59, 100, 0, 0.1)
    expect(left.ra).toBeGreaterThan(100)
    expect(up.dec).toBeGreaterThan(0)
  })
  it('skyToPixel invierte pixelToSky', () => {
    const s = pixelToSky(10.5, 47.2, 59, 59, 248.167, 66.755, 0.1)
    const p = skyToPixel(s.ra, s.dec, 59, 59, 248.167, 66.755, 0.1)
    expect(p.x).toBeCloseTo(10.5, 6)
    expect(p.y).toBeCloseTo(47.2, 6)
  })
  it('formatea WISE 0855 como el enunciado', () => {
    expect(formatRA(133.795129)).toBe('08h55m10.83s')
    expect(formatDec(-7.245147)).toBe('−07°14′42.5″')
  })
})

describe('vista en la URL (C4)', () => {
  it('ida y vuelta', () => {
    const v = { ...DEFAULT_VIEW, target: null, ra: 133.795, dec: -7.245, band: 23, det: 'D2' as const, t: 5, fov: 0.2, mask: ['SOURCE'], lang: 'es' as const }
    expect(parseView('?' + serializeView(v))).toEqual(v)
  })
  it('ignora basura', () => {
    const v = parseView('?band=999&det=D9&target=pluton&t=-3')
    expect(v.band).toBeNull()
    expect(v.det).toBeNull()
    expect(v.t).toBe(0)
  })
})

describe('i18n', () => {
  it('todas las claves existen en inglés y en español', () => {
    expect(missingKeys()).toEqual({ en: [], es: [] })
  })
})
