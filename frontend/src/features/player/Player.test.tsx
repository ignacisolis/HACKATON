// Prueba de humo del componente: monta el reproductor con estado falso y verifica lo que el usuario ve
// y que las acciones escriban la vista. Sin red: api y estado van mockeados.
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Frame } from '../../api/types'

const setView = vi.fn()
const view = {
  target: 'wise_0855', ra: null, dec: null, fov: 0.1, det: null, band: null as number | null, t: 0,
  stretch: 'asinh', zodi: false, mask: [] as string[], diff: null, pick: null, lang: 'es',
}

function fr(id: string, date: string, band: number, wl: number): Frame {
  return {
    id, mjd: Date.parse(date + 'Z') / 86400000 + 40587, date, detector: 'D2', wavelength_um: wl, bandwidth_um: 0.036,
    band, release: 'l2b-v20-2025-241', image_url: '', target_xy: [28.1, 29.07], flagged_fraction: 0.01, quality: 'ok', ready: true,
  }
}
const seq = [fr('a', '2025-05-06T10:44:49.776', 25, 1.3099), fr('b', '2025-11-07T18:52:29.517', 25, 1.3175), fr('c', '2025-12-12T01:49:35.537', 25, 1.3174)]
let frames = {
  query: { target: 'wise_0855', size: 0.1 }, coverage: null, detector: 'D2', loading: false, error: null as unknown, reload: vi.fn(),
  response: { query: { ra: 133.76, dec: -7.24, size: 0.1 }, n_frames: 48, n_dates: 14, pending: 1, complete: false, frames: seq },
  frames: seq, sequence: seq, current: seq[0],
}

vi.mock('../../state/view', () => ({ useView: () => ({ view, setView, shareUrl: '' }) }))
vi.mock('../../state/frames', () => ({ useFrames: () => frames }))
vi.mock('../../api/client', () => ({
  api: {
    frameImageUrl: (f: Frame, _q: unknown, o: { layer?: string }) => `/png/${f.id}/${o.layer ?? 'image'}`,
    frames: vi.fn(() => new Promise(() => {})),
  },
}))

const { default: Player } = await import('./Player')

let root: Root, el: HTMLDivElement
beforeEach(() => {
  setView.mockClear()
  el = document.createElement('div'); document.body.appendChild(el)
  root = createRoot(el)
})
afterEach(() => { act(() => root.unmount()); el.remove(); view.band = null; view.t = 0 })
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('Player', () => {
  it('muestra el cuadro, la etiqueta, el progreso de IRSA y el aviso de WISE 0855', () => {
    act(() => root.render(<Player />))
    const txt = el.textContent ?? ''
    expect(txt).toContain('Cuadro 1 de 3')
    expect(txt).toContain('2025-05-06 10:44 UTC')
    expect(txt).toContain('1.310 ± 0.018 µm')
    expect(txt).toContain('Descargando de IRSA: 47 de 48')
    expect(txt).toContain('WISE 0855 se mueve solo ~1.35 px')
    // mientras IRSA sigue bajando, "pocas fechas" puede ser transitorio: no se avisa todavía
    expect(txt).not.toContain('Solo 3 fechas')
    expect(txt).toContain('Precargando imágenes: 0 de 3')
    expect(el.querySelector<HTMLImageElement>('.pl-img')!.getAttribute('src')).toBe('/png/a/image')
    expect(el.querySelector('.pl-mask')).toBeNull()
  })

  it('flecha derecha avanza el cuadro (escribe view.t) y no actúa con el foco en un select', () => {
    act(() => root.render(<Player />))
    act(() => { window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' })) })
    expect(setView).toHaveBeenCalledWith({ t: 1 })
    setView.mockClear()
    const sel = el.querySelector('select')!
    act(() => { sel.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })) })
    expect(setView).not.toHaveBeenCalled()
  })

  it('con banda fija y pocos cuadros avisa y ofrece volver a todas las bandas', () => {
    view.band = 25
    act(() => root.render(<Player />))
    expect(el.textContent).toContain('Solo 3 cuadros en esta banda')
    const btn = [...el.querySelectorAll('button')].find(b => b.textContent === 'Usar todas las bandas')!
    act(() => btn.click())
    expect(setView).toHaveBeenCalledWith({ band: null, t: 0 })
  })

  it('con máscara prendida superpone la capa flags', () => {
    view.mask = ['SOURCE']
    act(() => root.render(<Player />))
    expect(el.querySelector('.pl-mask')!.getAttribute('src')).toBe('/png/a/flags')
    view.mask = []
  })

  it('error del backend con reintentar', () => {
    const prev = frames
    frames = { ...frames, sequence: [], frames: [], current: null as unknown as Frame, response: null as unknown as typeof frames.response, error: { code: 'irsa_unavailable', message: 'IRSA no responde' } }
    act(() => root.render(<Player />))
    expect(el.textContent).toContain('irsa_unavailable')
    const btn = [...el.querySelectorAll('button')].find(b => b.textContent === 'Reintentar')!
    act(() => btn.click())
    expect(frames.reload).toHaveBeenCalled()
    frames = prev
  })
})
