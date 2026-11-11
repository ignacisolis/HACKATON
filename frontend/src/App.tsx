// Armazón de la página. Cada área es dueña de su carpeta en features/ y entra acá por UN componente.
//   nav/      coordenadas, objetivos, Aladin (SkyContext)
//   player/   video del cielo, línea de tiempo, detector y banda
//   inspect/  metadata, capas de máscara FLAGS, resta de cuadros
//   science/  espectro y curva de luz
import { useState } from 'react'
import { USE_FIXTURES } from './api/client'
import { useT } from './i18n'
import { useView } from './state/view'
import NavPanel from './features/nav/NavPanel'
import SkyContext from './features/nav/SkyContext'
import Player from './features/player/Player'
import InspectPanel from './features/inspect/InspectPanel'
import SciencePanel from './features/science/SciencePanel'

function Header() {
  const t = useT()
  const { view, setView, shareUrl } = useView()
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try { await navigator.clipboard.writeText(shareUrl); setCopied(true); setTimeout(() => setCopied(false), 1800) } catch { /* sin permiso de portapapeles */ }
  }
  return (
    <header className="app-header">
      <div className="brand">
        <h1>{t('app.title')}</h1>
        <p className="muted">{t('app.tagline')}</p>
      </div>
      <div className="header-actions">
        {USE_FIXTURES && <span className="badge warn" title={t('app.fixturesMode')}>fixtures</span>}
        <button className="btn" onClick={copy} aria-live="polite">{copied ? t('app.copied') : t('app.share')}</button>
        <div className="seg" role="group" aria-label={t('app.lang')}>
          {(['en', 'es'] as const).map(l => (
            <button key={l} className={view.lang === l ? 'on' : ''} aria-pressed={view.lang === l}
              onClick={() => setView({ lang: l })}>{l.toUpperCase()}</button>
          ))}
        </div>
      </div>
    </header>
  )
}

export default function App() {
  const t = useT()
  return (
    <div className="app">
      <Header />
      <main className="layout">
        <aside className="col-nav">
          <section className="card"><NavPanel /></section>
          <section className="card"><SkyContext /></section>
        </aside>
        <section className="col-main">
          <div className="card"><Player /></div>
          <div className="card"><SciencePanel /></div>
        </section>
        <aside className="col-inspect">
          <section className="card"><InspectPanel /></section>
        </aside>
      </main>
      <footer className="app-footer muted">{t('app.footer')}</footer>
    </div>
  )
}
