// Humo: el panel se arma con los objetivos de respaldo antes de que responda la API.
// renderToString no corre efectos, así que no hay fetch.
import { describe, expect, it } from 'vitest'
import { renderToString } from 'react-dom/server'
import { FramesProvider } from '../../state/frames'
import { ViewProvider } from '../../state/view'
import NavPanel from './NavPanel'

function render(search: string) {
  window.history.replaceState(null, '', `/${search}`)
  return renderToString(<ViewProvider><FramesProvider><NavPanel /></FramesProvider></ViewProvider>)
}

describe('NavPanel', () => {
  it('muestra los 4 atajos y marca el activo', () => {
    const html = render('?target=wise_0855&lang=es')
    for (const n of ['Epsilon Indi B', 'WISE 0855-0714', 'RW Aurigae A', 'R Draconis']) expect(html).toContain(n)
    expect(html).toMatch(/aria-pressed="true"[^>]*><span class="nav-target-name">WISE 0855-0714/)
    expect(html).toContain('Dónde mirar')
    expect(html).not.toContain('Posición libre: no se corrige')
  })
  it('posición libre: rellena los campos y muestra el aviso de movimiento propio', () => {
    const html = render('?ra=133.79513&dec=-7.24515&lang=en')
    expect(html).toContain('value="133.79513"')
    expect(html).toContain('value="-7.24515"')
    expect(html).toContain('08h55m10.83s')
    expect(html).toContain('Use the WISE 0855-0714 shortcut')
    expect(html).toContain('https://aladin.cds.unistra.fr/AladinLite/?target=133.79513%20-7.24515')
  })
})
