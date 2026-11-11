import { describe, expect, it } from 'vitest'
import type { Detector, Frame, Quality } from '../../api/types'
import { bandOptions, buildSequence, dayKey, median, referenceWavelength, seasonStarts, sequenceStats, wavelengthRange } from './sequence'

// fecha ISO → mjd, para que mjd y date sean coherentes como en los datos reales
const mjdOf = (iso: string) => Date.parse(iso + 'Z') / 86400000 + 40587

function mk(id: string, date: string, band: number | null, wl: number | null, o: { q?: Quality; det?: Detector; ready?: boolean; bw?: number } = {}): Frame {
  const ready = o.ready ?? wl != null
  return {
    id, mjd: mjdOf(date), date, detector: o.det ?? 'D2',
    wavelength_um: ready ? wl : null, bandwidth_um: ready ? (o.bw ?? 0.036) : null, band: ready ? band : null,
    release: 'l2b-v20', image_url: '', target_xy: ready ? [29, 29] : null, flagged_fraction: ready ? 0.01 : null,
    quality: ready ? (o.q ?? 'ok') : null, ready,
  }
}

// Una visita real de WISE 0855 en D2: 4 exposiciones seguidas, cada una en otro canal.
const visitA = [
  mk('a1', '2025-05-06T02:34:27.489', 31, 1.5151),
  mk('a2', '2025-05-06T02:36:36.419', 32, 1.5524),
  mk('a3', '2025-05-06T10:42:40.846', 24, 1.2796),
  mk('a4', '2025-05-06T10:44:49.776', 25, 1.3099),
]
const visitB = [
  mk('b1', '2025-11-07T05:47:59.020', 18, 1.1011),
  mk('b2', '2025-11-07T18:52:29.517', 25, 1.3175),
  mk('b3', '2025-11-07T22:11:50.920', 33, 1.5921),
]
const visitC = [mk('c1', '2025-12-12T01:49:35.537', 25, 1.3174)]

describe('buildSequence con banda fija', () => {
  it('trae solo esa banda, ordenada por mjd aunque lleguen desordenados', () => {
    const all = [...visitC, ...visitB, ...visitA]
    const s = buildSequence(all, { band: 25 })
    expect(s.map(f => f.id)).toEqual(['a4', 'b2', 'c1'])
  })
  it('deja afuera los cuadros que todavía no bajaron (ready=false)', () => {
    const s = buildSequence([...visitA, mk('x', '2025-05-07T00:00:00.000', 25, null)], { band: 25 })
    expect(s.map(f => f.id)).toEqual(['a4'])
  })
  it('incluye cuadros "bad" (son pocos: el badge avisa)', () => {
    const s = buildSequence([mk('q', '2025-05-06T00:00:00.000', 7, 0.9, { q: 'bad' })], { band: 7 })
    expect(s).toHaveLength(1)
  })
})

describe('buildSequence con todas las bandas', () => {
  const all = [...visitA, ...visitB, ...visitC]

  it('un cuadro por día UTC, ordenado por mjd', () => {
    const s = buildSequence(all, { band: null })
    expect(s).toHaveLength(3)
    expect(s.map(dayKey)).toEqual(['2025-05-06', '2025-11-07', '2025-12-12'])
    for (let k = 1; k < s.length; k++) expect(s[k].mjd).toBeGreaterThan(s[k - 1].mjd)
  })

  it('elige en cada día la λ más cercana a la mediana del detector', () => {
    const ref = referenceWavelength(all)!
    expect(ref).toBeCloseTo(1.31745, 5) // mediana de las 8 λ
    const s = buildSequence(all, { band: null })
    expect(s.map(f => f.id)).toEqual(['a4', 'b2', 'c1'])
  })

  it('evita un cuadro "bad" si ese día hay otro, aunque esté más lejos en λ', () => {
    const d = [
      mk('m1', '2026-01-01T01:00:00.000', 25, 1.30),
      mk('m2', '2026-01-01T02:00:00.000', 26, 1.38),
      mk('m3', '2026-01-01T03:00:00.000', 27, 1.35, { q: 'bad' }),
      mk('n1', '2026-01-02T01:00:00.000', 27, 1.35, { q: 'bad' }),
    ]
    const s = buildSequence(d, { band: null })
    expect(s.map(f => f.id)).toEqual(['m2', 'n1']) // ref = 1.35; n1 es lo único del día 2
  })

  it('"suspect" pierde contra un "ok" a la misma distancia', () => {
    const d = [
      mk('s', '2026-01-01T01:00:00.000', 25, 1.30, { q: 'suspect' }),
      mk('o', '2026-01-01T02:00:00.000', 27, 1.40),
      mk('r', '2026-01-02T01:00:00.000', 26, 1.35),
    ]
    expect(buildSequence(d, { band: null })[0].id).toBe('o')
  })

  it('en empate de costo gana el más temprano', () => {
    const d = [mk('late', '2026-01-01T05:00:00.000', 26, 1.35), mk('early', '2026-01-01T01:00:00.000', 26, 1.35)]
    expect(buildSequence(d, { band: null }).map(f => f.id)).toEqual(['early'])
  })

  it('ignora los ready=false y no se rompe si no hay ninguno listo', () => {
    expect(buildSequence([mk('p', '2026-01-01T00:00:00.000', null, null)], { band: null })).toEqual([])
    expect(buildSequence([], { band: null })).toEqual([])
  })

  it('no mezcla detectores: un cuadro por día y por detector, cada uno con su λ de referencia', () => {
    const d = [
      mk('d2', '2026-01-01T01:00:00.000', 25, 1.3, { det: 'D2' }),
      mk('d5', '2026-01-01T01:05:00.000', 75, 4.0, { det: 'D5' }),
    ]
    expect(buildSequence(d, { band: null })).toHaveLength(2)
  })
})

describe('auxiliares', () => {
  it('median', () => {
    expect(median([])).toBeNull()
    expect(median([3, 1, 2])).toBe(2)
    expect(median([4, 1, 2, 3])).toBe(2.5)
  })
  it('dayKey usa el día UTC del ISO, y el mjd si no hay fecha', () => {
    expect(dayKey(visitA[0])).toBe('2025-05-06')
    expect(dayKey({ ...visitA[0], date: '' })).toBe('2025-05-06')
  })
  it('bandOptions agrupa por banda con la λ mediana y cuenta cuadros', () => {
    const o = bandOptions([...visitA, ...visitB, ...visitC, mk('p', '2026-01-01T00:00:00.000', null, null)])
    expect(o.map(x => x.band)).toEqual([18, 24, 25, 31, 32, 33])
    const b25 = o.find(x => x.band === 25)!
    expect(b25.count).toBe(3)
    expect(b25.wavelength_um).toBeCloseTo(1.3174, 4)
  })
  it('sequenceStats y wavelengthRange', () => {
    const s = buildSequence([...visitA, ...visitB, ...visitC], { band: null })
    const st = sequenceStats(s)
    expect(st.n).toBe(3)
    expect(st.days).toBe(3)
    expect(st.wlMin).toBeCloseTo(1.3099, 4)
    expect(st.wlMax).toBeCloseTo(1.3175, 4)
    expect(wavelengthRange(visitB)).toEqual([1.1011, 1.5921])
    expect(wavelengthRange([])).toBeNull()
  })
  it('seasonStarts marca el primer cuadro y los que siguen a un hueco largo', () => {
    const s = buildSequence([...visitA, ...visitB, ...visitC], { band: null })
    expect(seasonStarts(s)).toEqual([0, 1, 2]) // may → nov (185 d) → dic (35 d)
    expect(seasonStarts(s, 60)).toEqual([0, 1])
  })
})
