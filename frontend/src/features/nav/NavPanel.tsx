// Navegación: coordenadas (O2), atajos a los 4 objetivos (O5), tamaño del recorte y enlaces (C9).
// Todo lo que cambia la vista pasa por setView, que lo refleja en la URL (C4).
import { useId, useState, type ClipboardEvent, type FormEvent } from 'react'
import { useT } from '../../i18n'
import { formatDec, formatRA } from '../../lib/sky'
import { useView } from '../../state/view'
import ExternalLinks from './ExternalLinks'
import { parseCoordInputs, splitIfPair, type CoordError } from './parseCoords'
import { useCurrentPosition } from './position'
import { FOV_OPTIONS, fovToPixels, nearbyHighPmTarget, useTargets } from './targets'
import './nav.css'

const fmtDeg = (x: number) => `${x.toFixed(5)}°`

export default function NavPanel() {
  const t = useT()
  const { view, setView } = useView()
  const { list: targets, fromApi } = useTargets()
  const pos = useCurrentPosition(targets)
  const uid = useId()

  // Los campos se rellenan con la posición libre actual y se re-sincronizan cuando cambia desde
  // afuera (link, Aladin, atrás/adelante). Con un objetivo quedan vacíos.
  const posKey = view.target ? `t:${view.target}` : `${view.ra},${view.dec}`
  const initial = () => (!view.target && view.ra != null && view.dec != null)
    ? [view.ra.toFixed(5), view.dec.toFixed(5)] : ['', '']
  const [syncedKey, setSyncedKey] = useState(posKey)
  const [raText, setRaText] = useState(() => initial()[0])
  const [decText, setDecText] = useState(() => initial()[1])
  const [err, setErr] = useState<{ which: 'ra' | 'dec'; code: CoordError } | null>(null)
  if (syncedKey !== posKey) {
    const [r, d] = initial()
    setSyncedKey(posKey); setRaText(r); setDecText(d); setErr(null)
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const r = parseCoordInputs(raText, decText)
    if (!r.ok) { setErr({ which: r.which, code: r.error }); return }
    setErr(null)
    setRaText(r.raText); setDecText(r.decText)
    setView({ target: null, ra: r.ra, dec: r.dec })
  }

  const onPasteRa = (e: ClipboardEvent<HTMLInputElement>) => {
    const pair = splitIfPair(e.clipboardData.getData('text'))
    if (!pair) return
    e.preventDefault()
    setRaText(pair[0]); setDecText(pair[1]); setErr(null)
  }

  const errId = `${uid}-err`
  const helpId = `${uid}-help`
  const near = !view.target && pos ? nearbyHighPmTarget(pos.ra, pos.dec, targets) : null

  return (
    <div className="nav">
      <h2>{t('nav.title')}</h2>

      <form className="nav-form" onSubmit={submit} noValidate aria-label={t('nav.coords')}>
        <div className="nav-fields">
          <label className="nav-field">
            <span title={t('nav.raLong')}>{t('nav.ra')}</span>
            <input className="mono" value={raText} placeholder={t('nav.raPlaceholder')} spellCheck={false} autoComplete="off"
              aria-label={t('nav.raLong')} aria-invalid={err?.which === 'ra'} aria-describedby={err?.which === 'ra' ? errId : helpId}
              onChange={e => { setRaText(e.target.value); if (err?.which === 'ra') setErr(null) }} onPaste={onPasteRa} />
          </label>
          <label className="nav-field">
            <span title={t('nav.decLong')}>{t('nav.dec')}</span>
            <input className="mono" value={decText} placeholder={t('nav.decPlaceholder')} spellCheck={false} autoComplete="off"
              aria-label={t('nav.decLong')} aria-invalid={err?.which === 'dec'} aria-describedby={err?.which === 'dec' ? errId : helpId}
              onChange={e => { setDecText(e.target.value); if (err?.which === 'dec') setErr(null) }} />
          </label>
          <button type="submit" className="primary nav-go">{t('nav.go')}</button>
        </div>
        {err
          ? <p id={errId} className="nav-error" role="alert">{t(`nav.err.${err.which}.${err.code}`)}</p>
          : <p id={helpId} className="nav-help muted">{t('nav.coordsHelp')}</p>}
      </form>

      <div className="nav-current" aria-live="polite">
        <div className="nav-label muted">{t('nav.current')}</div>
        {pos ? (
          <>
            <div className="mono nav-sexa">{formatRA(pos.ra)} {formatDec(pos.dec)}</div>
            <div className="mono muted">{fmtDeg(pos.ra)} {pos.dec < 0 ? '−' : '+'}{fmtDeg(Math.abs(pos.dec))}</div>
            <div className="muted nav-help">{t(`nav.src.${pos.source}`)}</div>
          </>
        ) : <div className="muted">{t('nav.none')}</div>}
      </div>

      {!view.target && pos && (
        <div className="notice nav-pm">
          {near ? (
            <>
              <p>{t('nav.pmNear', { name: near.name, pm: near.pmArcsecYr.toFixed(1) })}</p>
              <button type="button" onClick={() => setView({ target: near.key })}>{t('nav.pmNearGo', { name: near.name })}</button>
            </>
          ) : <p>{t('nav.pmNote')}</p>}
        </div>
      )}

      <section className="nav-section" aria-labelledby={`${uid}-targets`}>
        <h3 id={`${uid}-targets`} className="nav-label muted">{t('nav.targets')}</h3>
        <ul className="nav-targets">
          {targets.map(tg => {
            const on = view.target === tg.key
            return (
              <li key={tg.key}>
                <button type="button" className={`nav-target${on ? ' on' : ''}`} aria-pressed={on}
                  onClick={() => setView({ target: tg.key })}>
                  <span className="nav-target-name">{tg.name}</span>
                  <span className="nav-target-hint">{t(`nav.hint.${tg.key}`)}</span>
                </button>
              </li>
            )
          })}
        </ul>
        {fromApi === false && <p className="nav-help muted">{t('nav.targetsOffline')}</p>}
      </section>

      <section className="nav-section" aria-labelledby={`${uid}-fov`}>
        <h3 id={`${uid}-fov`} className="nav-label muted">{t('nav.fov')}</h3>
        <div className="seg nav-fov" role="group" aria-labelledby={`${uid}-fov`}>
          {FOV_OPTIONS.map(f => (
            <button key={f} type="button" className={view.fov === f ? 'on' : ''} aria-pressed={view.fov === f}
              onClick={() => setView({ fov: f })}>
              <span className="mono">{f}°</span>
              <small>{t('nav.fovPx', { px: fovToPixels(f) })}</small>
            </button>
          ))}
        </div>
        <p className="nav-help muted">{t('nav.fovHelp')}</p>
      </section>

      <section className="nav-section" aria-labelledby={`${uid}-links`}>
        <h3 id={`${uid}-links`} className="nav-label muted">{t('nav.links')}</h3>
        <ExternalLinks pos={pos} fov={view.fov} />
      </section>
    </div>
  )
}
