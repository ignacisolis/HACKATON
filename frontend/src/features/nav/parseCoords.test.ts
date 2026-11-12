import { describe, expect, it } from 'vitest'
import { normalizeCoordText, parseCoordInputs, parseDec, parseRA, splitIfPair, splitPair } from './parseCoords'

// WISE 0855 del enunciado: 08h55m10.831s −07°14′42.53″ = 133.79512917, −7.24514722 (targets.yaml)
const WISE_RA = 133.79512917
const WISE_DEC = -7.24514722
const ARCSEC = 1 / 3600

const ra = (s: string) => { const r = parseRA(s); if (!r.ok) throw new Error(`RA "${s}": ${r.error}`); return r.deg }
const dec = (s: string) => { const r = parseDec(s); if (!r.ok) throw new Error(`Dec "${s}": ${r.error}`); return r.deg }
const raErr = (s: string) => { const r = parseRA(s); return r.ok ? null : r.error }
const decErr = (s: string) => { const r = parseDec(s); return r.ok ? null : r.error }

describe('parseRA', () => {
  it.each([
    ['133.795', 133.795],
    ['  133.795  ', 133.795],
    ['0', 0],
    ['359.9999', 359.9999],
    ['133,795', 133.795], // coma decimal
    ['+133.795', 133.795],
    ['133.795d', 133.795],
    ['133.795°', 133.795],
  ])('grados decimales: %s', (s, v) => expect(ra(s)).toBeCloseTo(v, 9))

  it.each([
    '08h55m10.831s', '08:55:10.831', '08 55 10.831', '8h55m10.831s', '08h 55m 10.831s',
    '08H55M10.831S', '08h55m10.831', '08 h 55 m 10.831 s', ' 08:55:10.831',
  ])('sexagesimal en horas: %s', s => expect(ra(s)).toBeCloseTo(WISE_RA, 6))

  it('horas sin segundos', () => expect(ra('08:55')).toBeCloseTo((8 + 55 / 60) * 15, 9))
  it('horas decimales con h', () => expect(ra('8.5h')).toBeCloseTo(127.5, 9))
  it('sexagesimal en grados si lleva d o °', () => {
    expect(ra('133d47m42.4645s')).toBeCloseTo(WISE_RA, 6)
    expect(ra('133°47′42.4645″')).toBeCloseTo(WISE_RA, 6)
  })
  it('error por rango', () => {
    expect(raErr('360')).toBe('range')
    expect(raErr('400')).toBe('range')
    expect(raErr('-10')).toBe('range')
    expect(raErr('24:00:00')).toBe('range')
    expect(raErr('25h')).toBe('range')
  })
  it('minutos o segundos ≥ 60', () => {
    expect(raErr('08:60:00')).toBe('minsec')
    expect(raErr('08:55:60')).toBe('minsec')
  })
  it('errores de formato', () => {
    expect(raErr('')).toBe('empty')
    expect(raErr('   ')).toBe('empty')
    expect(raErr('abc')).toBe('format')
    expect(raErr('08:55:10:01')).toBe('format') // 4 componentes
    expect(raErr('08.5:30')).toBe('format')     // decimales en un componente que no es el último
    expect(raErr('08h55d')).toBe('format')      // horas y grados mezclados
    expect(raErr('08:')).toBe('format')
    expect(raErr('1e3')).toBe('format')
    expect(raErr('08 55 10 -07')).toBe('format')
  })
})

describe('parseDec', () => {
  it.each([
    '-07d14m42.53s', '-07:14:42.53', '-7 14 42.53', '−07°14′42.53″', '-07°14\'42.53"',
    '–07:14:42.53', '-07d 14m 42.53s', "-07°14'42.53''", '-07D14M42.53S',
  ])('sexagesimal negativa: %s', s => expect(dec(s)).toBeCloseTo(WISE_DEC, 7))

  it('la trampa del signo con grados cero', () => {
    expect(dec('-00:30:00')).toBeCloseTo(-0.5, 12)
    expect(dec('-0 30 0')).toBeCloseTo(-0.5, 12)
    expect(dec('−00°30′00″')).toBeCloseTo(-0.5, 12)
    expect(dec('-00d00m36s')).toBeCloseTo(-0.01, 12)
    expect(dec('+00:30:00')).toBeCloseTo(0.5, 12)
    expect(dec('00:30:00')).toBeCloseTo(0.5, 12)
  })
  it('decimal', () => {
    expect(dec('-7.245')).toBe(-7.245)
    expect(dec('+66.755')).toBe(66.755)
    expect(dec('66.755')).toBe(66.755)
    expect(dec('-7,245')).toBe(-7.245)
    expect(dec('90')).toBe(90)
    expect(dec('-90')).toBe(-90)
  })
  it('sin -0', () => expect(Object.is(dec('-0'), 0)).toBe(true))
  it('positiva sexagesimal', () => expect(dec('+66 45 17.93')).toBeCloseTo(66 + 45 / 60 + 17.93 / 3600, 9))
  it('rango', () => {
    expect(decErr('90.0001')).toBe('range')
    expect(decErr('-91')).toBe('range')
    expect(decErr('90:00:01')).toBe('range')
  })
  it('minutos o segundos ≥ 60', () => {
    expect(decErr('-07:60:00')).toBe('minsec')
    expect(decErr('-07:14:61')).toBe('minsec')
  })
  it('formato', () => {
    expect(decErr('')).toBe('empty')
    expect(decErr('-07h14m')).toBe('format') // horas en la Dec
    expect(decErr('--7')).toBe('format')
    expect(decErr('+-7')).toBe('format')
    expect(decErr('7 -14')).toBe('format')
    expect(decErr('norte')).toBe('format')
  })
})

describe('normalizeCoordText', () => {
  it('unifica signos menos y primas tipográficas', () => {
    expect(normalizeCoordText(' −07°14′42.53″ ')).toBe(`-07°14'42.53"`)
    expect(normalizeCoordText('–07')).toBe('-07')
  })
})

describe('splitPair / pegar RA y Dec juntas', () => {
  it.each([
    ['08h55m10.831s -07d14m42.53s', '08h55m10.831s', '-07d14m42.53s'],
    ['08h55m10.831s−07d14m42.53s', '08h55m10.831s', '-07d14m42.53s'],
    ['133.795 -7.245', '133.795', '-7.245'],
    ['133.795, -7.245', '133.795', '-7.245'],
    ['133.795,-7.245', '133.795', '-7.245'],
    ['133.795 7.245', '133.795', '7.245'],
    ['08:55:10.831 -07:14:42.53', '08:55:10.831', '-07:14:42.53'],
    ['08 55 10.831 -07 14 42.53', '08 55 10.831', '-07 14 42.53'],
    ['16 32 40.2 +66 45 17.9', '16 32 40.2', '+66 45 17.9'],
    ['16 32 40.2 66 45 17.9', '16 32 40.2', '66 45 17.9'],
    ['08:55:10.831 +00:30:00', '08:55:10.831', '+00:30:00'],
    ['08:55:10.831 -00:30:00', '08:55:10.831', '-00:30:00'],
  ])('%s', (s, a, b) => expect(splitPair(s)).toEqual([a, b]))

  it('no parte una sola coordenada', () => {
    expect(splitPair('133.795')).toBeNull()
    expect(splitPair('08h55m10.831s')).toBeNull()
    expect(splitPair('')).toBeNull()
    expect(splitPair('133.795 -95')).toBeNull()
  })
  it('splitIfPair respeta una RA válida por sí sola ("08 55" es 08h55m)', () => {
    expect(splitIfPair('08 55')).toBeNull()
    expect(splitIfPair('133.795 -7.245')).toEqual(['133.795', '-7.245'])
  })
})

describe('parseCoordInputs (lo que hace el formulario)', () => {
  it('dos campos', () => {
    const r = parseCoordInputs('08h55m10.831s', '-07d14m42.53s')
    expect(r.ok).toBe(true)
    if (r.ok) { expect(r.ra).toBeCloseTo(WISE_RA, 6); expect(r.dec).toBeCloseTo(WISE_DEC, 7) }
  })
  it('las dos en el campo RA con la Dec vacía', () => {
    const r = parseCoordInputs('08h55m10.831s -07d14m42.53s', '')
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(Math.abs(r.ra - WISE_RA)).toBeLessThan(0.01 * ARCSEC * 15)
      expect(Math.abs(r.dec - WISE_DEC)).toBeLessThan(0.01 * ARCSEC)
      expect(r.raText).toBe('08h55m10.831s')
      expect(r.decText).toBe('-07d14m42.53s')
    }
  })
  it('falta la Dec', () => expect(parseCoordInputs('08 55', '')).toEqual({ ok: false, error: 'empty', which: 'dec' }))
  it('error en RA tiene prioridad', () => expect(parseCoordInputs('25h', 'x')).toEqual({ ok: false, error: 'range', which: 'ra' }))
  it('error en Dec', () => expect(parseCoordInputs('133.795', '-95')).toEqual({ ok: false, error: 'range', which: 'dec' }))
})
