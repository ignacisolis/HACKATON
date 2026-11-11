import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import spectrumFx from '../../../../contracts/fixtures/spectrum.json'
import { ApiError } from '../../api/client'
import type { LightCurveResponse, SkyQuery, SpectrumResponse } from '../../api/types'
import { missingKeys } from '../../i18n'
import { ViewProvider } from '../../state/view'
import science from './i18n'
import SciencePanel from './SciencePanel'

const mocks = vi.hoisted(() => ({
  spectrum: vi.fn<(q: SkyQuery, s?: AbortSignal) => Promise<SpectrumResponse>>(),
  lightcurve: vi.fn<(q: SkyQuery, band: number, s?: AbortSignal) => Promise<LightCurveResponse>>(),
}))

vi.mock('../../api/client', async orig => {
  const real = await orig<typeof import('../../api/client')>()
  return { ...real, USE_FIXTURES: false, api: { ...real.api, spectrum: mocks.spectrum, lightcurve: mocks.lightcurve } }
})
vi.mock('../../state/frames', () => ({ useFrames: () => ({ current: { mjd: 60900 } }) }))

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let root: Root, host: HTMLDivElement
const flush = () => act(async () => { await new Promise(r => setTimeout(r, 0)) })

async function mount(search: string) {
  window.history.replaceState(null, '', `/${search}`)
  host = document.createElement('div')
  document.body.appendChild(host)
  root = createRoot(host)
  await act(async () => { root.render(<ViewProvider><SciencePanel /></ViewProvider>) })
  await flush()
}

beforeEach(() => { mocks.spectrum.mockReset(); mocks.lightcurve.mockReset() })
afterEach(() => { act(() => root.unmount()); host.remove() })

describe('SciencePanel', () => {
  it('501: avisa que el espectro no está disponible y no dibuja nada', async () => {
    mocks.spectrum.mockRejectedValue(new ApiError(501, { error: 'not_implemented', detail: 'core.extract_spectrum' }))
    await mount('?target=r_dra&lang=es')
    expect(host.textContent).toContain('todavía no está disponible en este servidor')
    expect(host.querySelector('svg.sci-svg')).toBeNull()
    expect(mocks.spectrum).toHaveBeenCalledWith({ target: 'r_dra', size: 0.1 }, expect.anything())
  })

  it('error genérico: ofrece reintentar y reintenta', async () => {
    mocks.spectrum.mockRejectedValueOnce(new ApiError(500, { error: 'boom', detail: 'algo falló' }))
    mocks.spectrum.mockResolvedValueOnce(structuredClone(spectrumFx) as unknown as SpectrumResponse)
    await mount('?target=r_dra&lang=en')
    const retry = [...host.querySelectorAll('button')].find(b => b.textContent === 'Retry')!
    expect(host.textContent).toContain('algo falló')
    await act(async () => { retry.click() })
    await flush()
    expect(mocks.spectrum).toHaveBeenCalledTimes(2)
    expect(host.querySelector('svg.sci-svg')).not.toBeNull()
  })

  it('usa el punto clickeado si existe y deja volver al objetivo', async () => {
    mocks.spectrum.mockRejectedValue(new ApiError(501, { error: 'not_implemented', detail: '' }))
    await mount('?target=r_dra&pra=248.2&pdec=66.7&lang=es')
    expect(mocks.spectrum).toHaveBeenLastCalledWith({ ra: 248.2, dec: 66.7, size: 0.1 }, expect.anything())
    const back = [...host.querySelectorAll('button')].find(b => b.textContent === 'Volver al objetivo')!
    await act(async () => { back.click() })
    await flush()
    expect(mocks.spectrum).toHaveBeenLastCalledWith({ target: 'r_dra', size: 0.1 }, expect.anything())
    expect(window.location.search).not.toContain('pra=')
  })

  it('dibuja el espectro y, al elegir una banda, la pasa a la vista y carga su curva de luz', async () => {
    mocks.spectrum.mockResolvedValue(structuredClone(spectrumFx) as unknown as SpectrumResponse)
    mocks.lightcurve.mockResolvedValue({ mjds: [60800, 60850, 60950], flux: [1, 2, 1.5], flux_err: [0.1, 0.1, 0.1] })
    await mount('?target=r_dra&lang=es')
    expect(host.querySelectorAll('.sci-svg .sci-pt')).toHaveLength(102)
    expect(host.querySelector('.sci-svg title')?.textContent).toBe('Espectro instantáneo')
    expect(host.textContent).toContain('2483 visitas combinadas')
    expect(host.textContent).toContain('Hacé click en un punto del espectro')
    expect(mocks.lightcurve).not.toHaveBeenCalled()

    const choose = host.querySelector<HTMLButtonElement>('button[aria-label="Elegir la banda 24 de D3"]')!
    await act(async () => { choose.click() })
    await flush()
    expect(window.location.search).toContain('band=24')
    expect(window.location.search).toContain("det=D3")
    expect(mocks.lightcurve).toHaveBeenCalledWith({ target: 'r_dra', size: 0.1 }, 24, expect.anything())
    expect(host.textContent).toContain('3 mediciones en 150 días')
    expect(host.querySelectorAll('.sci-svg')).toHaveLength(2)
    expect(host.querySelector('.sci-now')).not.toBeNull() // cuadro del video (mjd 60900) dentro del rango
    expect(host.querySelectorAll('.sci-selring').length).toBeGreaterThanOrEqual(1)
  })

  it('las referencias moleculares están apagadas por defecto', async () => {
    mocks.spectrum.mockResolvedValue(structuredClone(spectrumFx) as unknown as SpectrumResponse)
    await mount('?target=r_dra&lang=en')
    expect(host.querySelector('.sci-ref')).toBeNull()
    const toggle = [...host.querySelectorAll('label')].find(l => l.textContent?.includes('Molecular'))!.querySelector('input')!
    await act(async () => { toggle.click() })
    expect(host.querySelectorAll('.sci-ref').length).toBe(10)
    expect(host.textContent).toContain('approximate')
  })
})

describe('i18n de science', () => {
  it('cada clave está en inglés y en español', () => {
    expect(Object.keys(science.en).sort()).toEqual(Object.keys(science.es).sort())
    const m = missingKeys()
    expect(m.en.filter(k => k.startsWith('science.'))).toEqual([])
    expect(m.es.filter(k => k.startsWith('science.'))).toEqual([])
  })
})
