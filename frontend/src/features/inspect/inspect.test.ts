import { describe, expect, it } from 'vitest'
import metaFx from '../../../../contracts/fixtures/frame-meta.json'
import type { Frame, FrameMeta } from '../../api/types'
import { bitGroup, fullFrameRows, groupCounts, targetLayers, toggleMask } from './bits'
import dict from './i18n'
import {
  candidates, classifyDiff, compareHint, cutoutPixels, defaultReference, fmtCollection, fmtDateUtc,
  fmtPct, qualityReasons, readExtras, resolvingPower,
} from './logic'

const frame = (id: string, mjd: number, o: Partial<Frame> = {}): Frame => ({
  id, mjd, date: '2025-06-08T18:55:19.221', detector: 'D2', wavelength_um: 1.5, bandwidth_um: 0.04, band: 24,
  release: 'r', image_url: '', target_xy: [29, 29], flagged_fraction: 0, quality: 'ok', ready: true, ...o,
})

const meta = (o: Record<string, unknown> = {}): FrameMeta => ({ ...(structuredClone(metaFx) as unknown as FrameMeta), ...o })

describe('comparabilidad del lado del cliente', () => {
  const a = frame('a', 60800)
  it('distinto detector: no', () => {
    expect(compareHint(a, frame('b', 60900, { detector: 'D3' }))).toMatchObject({ level: 'unlikely', reason: 'detector' })
  })
  it('misma regla que core.is_comparable: |Δλ| ≤ 0.5 · min(ancho)', () => {
    expect(compareHint(a, frame('b', 60900, { wavelength_um: 1.519 })).level).toBe('likely') // 0.019 ≤ 0.02
    const far = compareHint(a, frame('b', 60900, { wavelength_um: 1.53 }))
    expect(far.level).toBe('unlikely')
    expect(far.dlam).toBeCloseTo(0.03, 6)
    expect(far.tol).toBeCloseTo(0.02, 6)
  })
  it('sin λ (ready=false) cae a la banda, y sin banda no se sabe', () => {
    const noLam = { wavelength_um: null, bandwidth_um: null }
    expect(compareHint(a, frame('b', 1, { ...noLam, band: 24 })).reason).toBe('band_ok')
    expect(compareHint(a, frame('b', 1, { ...noLam, band: 30 })).level).toBe('unlikely')
    expect(compareHint(a, frame('b', 1, { ...noLam, band: null })).level).toBe('unknown')
  })
  it('el mismo cuadro no es candidato', () => {
    expect(compareHint(a, a).reason).toBe('same')
    expect(candidates(a, [a]).likely).toHaveLength(0)
  })
})

describe('cuadro B por defecto', () => {
  const a = frame('a', 60850)
  const frames = [
    a,
    frame('near', 60851),
    frame('far', 60800),
    frame('farther-but-other-lambda', 60500, { wavelength_um: 2.0 }),
    frame('unknown', 60400, { wavelength_um: null, bandwidth_um: null, band: null }),
  ]
  it('elige el comparable más lejano en el tiempo, nunca uno no comparable', () => {
    expect(defaultReference(a, frames)?.id).toBe('far')
  })
  it('si no hay comparables probables, el más lejano de los dudosos', () => {
    expect(defaultReference(a, frames.filter(f => f.id !== 'far' && f.id !== 'near'))?.id).toBe('unknown')
  })
  it('null si solo hay no comparables o no hay A', () => {
    expect(defaultReference(a, [a, frame('x', 1, { detector: 'D5' })])).toBeNull()
    expect(defaultReference(null, frames)).toBeNull()
  })
  it('candidatos ordenados por |Δt| descendente', () => {
    expect(candidates(a, frames).likely.map(c => c.frame.id)).toEqual(['far', 'near'])
  })
})

describe('estado de la resta según el backend', () => {
  it('ok, 422, 404 de ruta, 501, red y otros', () => {
    expect(classifyDiff(null)).toEqual({ kind: 'ok' })
    expect(classifyDiff({ status: 422, code: 'not_comparable', message: 'distinto detector' }))
      .toEqual({ kind: 'not_comparable', detail: 'distinto detector' })
    expect(classifyDiff({ status: 404, code: 'not_found', message: 'Not Found' }).kind).toBe('pending_backend')
    expect(classifyDiff({ status: 501, code: 'not_implemented', message: '' }).kind).toBe('pending_backend')
    expect(classifyDiff({ status: 0, code: 'network', message: 'x' }).kind).toBe('network')
    // un 404 con otro detalle (p. ej. cuadro inexistente) NO es "endpoint pendiente"
    expect(classifyDiff({ status: 404, code: 'not_found', message: 'frame 123 no existe' }).kind).toBe('error')
    expect(classifyDiff({ status: 500, code: 'boom', message: 'x' })).toEqual({ kind: 'error', status: 500, detail: 'x' })
  })
})

describe('bits de FLAGS', () => {
  it('SOURCE es informativo, SUR_ERROR se excluye de la fotometría, TRANSIENT es contaminación', () => {
    expect(bitGroup('SOURCE')).toBe('info')
    expect(bitGroup('SUR_ERROR')).toBe('photometry')
    expect(bitGroup('TRANSIENT')).toBe('contamination')
    expect(bitGroup('MISSING')).toBe('photometry') // alias del header
    expect(bitGroup('BIT_3', 3)).toBe('unknown')
  })
  it('agrupa en orden y ordena por píxeles', () => {
    const g = groupCounts(meta().flags.cutout_counts)
    expect(g.map(x => x.group)).toEqual(['photometry', 'contamination', 'info'])
    expect(g[0].rows.map(r => r.name)).toEqual(['SUR_ERROR', 'PERSIST'])
    expect(g[1].rows.map(r => r.name)).toEqual(['TRANSIENT', 'OVERFLOW'])
  })
  it('toggle sin duplicar y capas del objetivo', () => {
    expect(toggleMask(['SOURCE'], 'HOT')).toEqual(['SOURCE', 'HOT'])
    expect(toggleMask(['SOURCE', 'HOT'], 'SOURCE')).toEqual(['HOT'])
    expect(targetLayers(['SOURCE', 'NONFUNC'], ['SOURCE', 'TRANSIENT'])).toEqual(['SOURCE'])
    expect(targetLayers(undefined, ['SOURCE'])).toEqual([])
  })
  it('cuentas de la exposición completa sin ceros y ordenadas', () => {
    expect(fullFrameRows({ A: 0, B: 5, C: 50 }).map(r => r.name)).toEqual(['C', 'B'])
  })
})

describe('metadata', () => {
  it('lee los extras del backend real y tolera formas raras', () => {
    const x = readExtras(meta({ shape: [85, 85], dqa: { l1: 'Pass', l2: 'Pass' }, target: { xy: [28.1, 29.1], inside: true }, flagged_fraction: 'no' }))
    expect(x.shape).toEqual([85, 85])
    expect(x.target?.xy).toEqual([28.1, 29.1])
    expect(x.flagged_fraction).toBeUndefined()
    expect(readExtras(meta({ target: 'raro', shape: [1] }))).toEqual({})
  })
  it('píxeles del recorte: de shape o deducidos de una fila', () => {
    expect(cutoutPixels(meta({ shape: [85, 85] }))).toBe(7225)
    expect(cutoutPixels(meta())).toBe(841) // fixture de R Dra: 29×29
  })
  it('motivos de quality', () => {
    const m = meta({
      target: { inside: false }, dqa: { l2: 'Fail' }, flagged_fraction: 0.6,
      flags: { ...meta().flags, at_target: ['SOURCE', 'HOT'] },
    })
    expect(qualityReasons(m).map(r => r.key)).toEqual(['outside', 'l2_qa', 'target_masked', 'over_half'])
    expect(qualityReasons(m).find(r => r.key === 'target_masked')).toEqual({ key: 'target_masked', bits: ['HOT'] })
    // SOURCE en el objetivo NO vuelve dudoso el cuadro: no está en la máscara de fotometría
    expect(qualityReasons(meta({ flags: { ...meta().flags, at_target: ['SOURCE'] } }))).toEqual([])
  })
  it('formatos', () => {
    expect(fmtDateUtc('2025-05-05T16:49:00.018')).toBe('2025-05-05 16:49:00 UTC')
    expect(fmtCollection('spherex_qr3_deep')).toBe('QR3 deep')
    expect(fmtCollection('spherex_qr2')).toBe('QR2')
    expect(fmtCollection('otra')).toBe('otra')
    expect(fmtPct(0.45, 'en')).toBe('45 %')
    expect(fmtPct(0.0201, 'en')).toBe('2.0 %')
    expect(fmtPct(0.0201, 'es')).toBe('2,0 %')
    expect(fmtPct(0.0001, 'en')).toBe('<0.1 %')
    expect(fmtPct(0, 'en')).toBe('0 %')
    expect(resolvingPower(1.5143, 0.0366)).toBe(41)
  })
})

describe('i18n de inspect', () => {
  it('todas las claves en los dos idiomas y con prefijo inspect.', () => {
    const en = Object.keys(dict.en), es = Object.keys(dict.es)
    expect(en.filter(k => !(k in dict.es))).toEqual([])
    expect(es.filter(k => !(k in dict.en))).toEqual([])
    expect(en.every(k => k.startsWith('inspect.'))).toBe(true)
  })
})
