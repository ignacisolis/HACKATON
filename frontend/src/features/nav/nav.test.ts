import { describe, expect, it } from 'vitest'
import dict from './i18n'
import { pickPosition } from './position'
import {
  NAV_TARGETS_FALLBACK, aladinUrl, angularSepDeg, contextFov, findTarget, fovCorners, fovToPixels,
  nearbyHighPmTarget, simbadCoordUrl, simbadIdUrl,
} from './targets'

describe('i18n de nav', () => {
  it('toda clave está en inglés y en español', () => {
    const en = Object.keys(dict.en).sort(), es = Object.keys(dict.es).sort()
    expect(es).toEqual(en)
    expect(en.length).toBeGreaterThan(0)
    expect(en.every(k => k.startsWith('nav.'))).toBe(true)
  })
  it('hay una línea de "qué mirar" por objetivo y un error por campo y código', () => {
    for (const tg of NAV_TARGETS_FALLBACK) expect(dict.en[`nav.hint.${tg.key}`]).toBeTruthy()
    for (const w of ['ra', 'dec']) for (const c of ['empty', 'format', 'range', 'minsec']) {
      expect(dict.en[`nav.err.${w}.${c}`]).toBeTruthy()
      expect(dict.es[`nav.err.${w}.${c}`]).toBeTruthy()
    }
  })
})

describe('objetivos de respaldo', () => {
  it('son los 4, en el orden de la demo', () => {
    expect(NAV_TARGETS_FALLBACK.map(t => t.key)).toEqual(['eps_ind_b', 'wise_0855', 'rw_aur', 'r_dra'])
  })
  it('coinciden con /api/targets a menos de medio píxel', () => {
    // valores que devolvió el backend el 2026-11-11 (coord_epoch_applied 2026-01-12)
    const api = { eps_ind_b: [331.09673, -56.80067], wise_0855: [133.7597, -7.24218], rw_aur: [76.95609, 30.40113], r_dra: [248.16723, 66.75502] }
    for (const t of NAV_TARGETS_FALLBACK) {
      const [ra, dec] = api[t.key]
      expect(angularSepDeg(t.ra, t.dec, ra, dec) * 3600).toBeLessThan(3.1)
    }
  })
  it('WISE 0855: el enunciado está a ~21 px de donde lo ve SPHEREx', () => {
    const w = findTarget(NAV_TARGETS_FALLBACK, 'wise_0855')!
    const px = (angularSepDeg(w.ra, w.dec, w.statement!.ra, w.statement!.dec) * 3600) / 6.2
    expect(px).toBeGreaterThan(18)
    expect(px).toBeLessThan(24)
  })
})

describe('geometría', () => {
  it('separación angular', () => {
    expect(angularSepDeg(10, 0, 11, 0)).toBeCloseTo(1, 9)
    expect(angularSepDeg(0, 60, 2, 60)).toBeCloseTo(1, 2) // cos(60°)·2°
    expect(angularSepDeg(359.5, 0, 0.5, 0)).toBeCloseTo(1, 9)
  })
  it('esquinas del recorte: lado = fov en el cielo', () => {
    const c = fovCorners(248.167, 66.755, 0.1)
    expect(c).toHaveLength(4)
    expect(angularSepDeg(c[0][0], c[0][1], c[3][0], c[3][1])).toBeCloseTo(0.1, 6) // lado este, N–S
    expect(angularSepDeg(c[0][0], c[0][1], c[1][0], c[1][1])).toBeCloseTo(0.1, 3) // lado norte, E–O
    expect(c[0][0]).toBeGreaterThan(248.167) // este a la izquierda = RA mayor
  })
  it('esquinas que cruzan RA 0', () => {
    for (const [ra] of fovCorners(0.01, 0, 0.1)) expect(ra >= 0 && ra < 360).toBe(true)
  })
  it('equivalencia en píxeles (~6.2″/px)', () => {
    expect([0.05, 0.1, 0.2, 0.3].map(fovToPixels)).toEqual([29, 58, 116, 174])
  })
  it('campo de Aladin con margen', () => {
    expect(contextFov(0.1)).toBeCloseTo(0.3, 9)
    expect(contextFov(0.05)).toBe(0.2)
    expect(contextFov(0.3)).toBeCloseTo(0.9, 9)
  })
})

describe('aviso de movimiento propio', () => {
  it('las coordenadas del enunciado de WISE 0855 disparan el atajo', () => {
    expect(nearbyHighPmTarget(133.79512917, -7.24514722, NAV_TARGETS_FALLBACK)?.key).toBe('wise_0855')
  })
  it('la J2000 de eps Ind B también', () => {
    expect(nearbyHighPmTarget(331.04414659, -56.7828442, NAV_TARGETS_FALLBACK)?.key).toBe('eps_ind_b')
  })
  it('R Dra no (no necesita corrección) ni un punto cualquiera', () => {
    expect(nearbyHighPmTarget(248.16761, 66.75498, NAV_TARGETS_FALLBACK)).toBeNull()
    expect(nearbyHighPmTarget(10, 10, NAV_TARGETS_FALLBACK)).toBeNull()
  })
})

describe('enlaces externos', () => {
  it('Aladin', () => {
    expect(aladinUrl(133.7597, -7.24218, 0.1))
      .toBe('https://aladin.cds.unistra.fr/AladinLite/?target=133.75970%20-7.24218&fov=0.1')
    expect(aladinUrl(248.16723, 66.75502, 0.2)).toContain('target=248.16723%20%2B66.75502&fov=0.2')
  })
  it('SIMBAD por coordenadas', () => {
    expect(simbadCoordUrl(76.95609, 30.40113))
      .toBe('https://simbad.cds.unistra.fr/simbad/sim-coo?Coord=76.95609%20%2B30.40113&Radius=30&Radius.unit=arcsec')
  })
  it('SIMBAD por nombre', () => {
    expect(simbadIdUrl('* eps Ind B')).toBe('https://simbad.cds.unistra.fr/simbad/sim-id?Ident=*%20eps%20Ind%20B')
  })
})

describe('pickPosition', () => {
  const free = { target: null, ra: 10, dec: -5 }
  it('posición libre: la de la URL', () => {
    expect(pickPosition(free, [], NAV_TARGETS_FALLBACK)).toMatchObject({ ra: 10, dec: -5, source: 'free', target: null })
    expect(pickPosition({ target: null, ra: null, dec: null }, [], NAV_TARGETS_FALLBACK)).toBeNull()
  })
  it('objetivo: gana lo que devuelve el backend', () => {
    const p = pickPosition({ target: 'wise_0855', ra: null, dec: null },
      [{ ra: 133.7601, dec: -7.24221, size: 0.1, target: 'wise_0855' }], NAV_TARGETS_FALLBACK)
    expect(p).toMatchObject({ ra: 133.7601, dec: -7.24221, source: 'backend' })
    expect(p?.target?.key).toBe('wise_0855')
  })
  it('descarta una respuesta vieja de otro objetivo o de una posición libre', () => {
    const p = pickPosition({ target: 'wise_0855', ra: null, dec: null },
      [{ ra: 1, dec: 2, size: 0.1, target: 'r_dra' }, { ra: 3, dec: 4, size: 0.1, target: null }], NAV_TARGETS_FALLBACK)
    expect(p?.source).toBe('targets')
    expect(p?.ra).toBeCloseTo(133.7597, 3)
  })
})
