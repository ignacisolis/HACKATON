// Prueba de humo del panel: monta las tres pestañas con la API y los cuadros simulados.
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import metaFx from '../../../../contracts/fixtures/frame-meta.json'
import type { Frame, FrameMeta } from '../../api/types'
import { ViewProvider } from '../../state/view'

const frame = (id: string, mjd: number, lam = 1.5): Frame => ({
  id, mjd, date: '2025-06-08T18:55:19.221', detector: 'D2', wavelength_um: lam, bandwidth_um: 0.04, band: 24,
  release: 'r', image_url: '', target_xy: [29, 29], flagged_fraction: 0.01, quality: 'ok', ready: true,
})
const FRAMES = [frame('f1', 60800), frame('f2', 60850), frame('f3', 60900), frame('f4', 60950, 2.2)]

vi.mock('../../state/frames', () => ({
  useFrames: () => ({
    query: { target: 'wise_0855', size: 0.1 }, frames: FRAMES, sequence: FRAMES, current: FRAMES[2],
    loading: false, error: null, coverage: null, detector: 'D2', response: null, reload: () => {},
  }),
}))

vi.mock('../../api/client', async () => {
  const { ApiError } = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return {
    ApiError,
    api: {
      meta: vi.fn(async (f: Frame) => ({ ...(structuredClone(metaFx) as unknown as FrameMeta), id: f.id,
        flags: { ...(metaFx as unknown as FrameMeta).flags, at_target: ['SOURCE'] } })),
      diffCheck: vi.fn(async () => new ApiError(404, { error: 'not_found', detail: 'Not Found' })),
      diffImageUrl: () => '/api/diff?x',
      frameImageUrl: () => '/api/frame/x/png',
    },
  }
})

const { default: InspectPanel } = await import('./InspectPanel')

let el: HTMLDivElement, root: Root
const flush = async (ms = 400) => { await act(async () => { await new Promise(r => setTimeout(r, ms)) }) }
const tab = (name: RegExp) => [...el.querySelectorAll<HTMLButtonElement>('[role=tab]')].find(b => name.test(b.textContent ?? ''))!

beforeEach(() => {
  ;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  window.history.replaceState(null, '', '/?target=wise_0855&lang=es')
  el = document.createElement('div'); document.body.appendChild(el)
  root = createRoot(el)
})
afterEach(() => { act(() => root.unmount()); el.remove() })

describe('InspectPanel', () => {
  it('muestra metadata, prende capas y propone la resta', async () => {
    await act(async () => { root.render(<ViewProvider><InspectPanel /></ViewProvider>) })
    expect(el.querySelectorAll('[role=tab]')).toHaveLength(3)
    await flush()
    expect(el.textContent).toContain('l2b-v20-2025-251')
    expect(el.textContent).toContain('Calidad')

    await act(async () => { tab(/Máscaras/).click() })
    await flush()
    const toggle = el.querySelector<HTMLInputElement>('input[aria-label="Mostrar SUR_ERROR sobre la imagen"]')!
    await act(async () => { toggle.click() })
    expect(window.location.search).toContain('mask=SUR_ERROR')
    expect(el.textContent).toContain('Exposición completa 2040×2040 (no es el recorte)')

    await act(async () => { tab(/Resta/).click() })
    await flush()
    // B sugerido: el comparable más lejano en el tiempo (f1; f4 tiene otra λ)
    expect(window.location.search).toContain('diff=f1')
    expect(el.textContent).toContain('pendiente en el backend')
  })
})
