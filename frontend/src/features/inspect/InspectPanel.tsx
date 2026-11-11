// Panel de inspección del cuadro actual: Metadata · Máscaras · Resta (C5, C6).
// El cuadro actual lo elige el reproductor (useFrames().current); acá solo se lee y se escribe la
// vista (view.mask, view.diff).
import { useId, useRef, useState, type KeyboardEvent } from 'react'
import { useT } from '../../i18n'
import { useFrames } from '../../state/frames'
import { useView } from '../../state/view'
import DiffTab from './DiffTab'
import MasksTab from './MasksTab'
import MetaTab from './MetaTab'
import { useFrameMeta } from './useFrameMeta'
import './inspect.css'

type Tab = 'meta' | 'masks' | 'diff'
const TABS: Tab[] = ['meta', 'masks', 'diff']

export default function InspectPanel() {
  const t = useT()
  const { view } = useView()
  const { query, current, frames, loading, error } = useFrames()
  // si el link trae una resta, se abre directo en esa pestaña
  const [tab, setTab] = useState<Tab>(() => (view.diff ? 'diff' : 'meta'))
  const id = useId()
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([])
  // la metadata solo hace falta en Metadata y Máscaras (en Resta no se pide un /meta por cuadro)
  const m = useFrameMeta(tab === 'diff' ? null : current, query)

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    let next = -1
    if (e.key === 'ArrowRight') next = (i + 1) % TABS.length
    else if (e.key === 'ArrowLeft') next = (i - 1 + TABS.length) % TABS.length
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = TABS.length - 1
    if (next < 0) return
    e.preventDefault()
    setTab(TABS[next])
    tabRefs.current[next]?.focus()
  }

  const body = (k: Tab) => {
    if (!query) return <p className="placeholder">{t('inspect.noPosition')}</p>
    if (!current) {
      if (error) return <p className="notice error" role="alert">{t('inspect.framesError', { detail: error.message })}</p>
      if (loading) return <p className="muted" role="status">{t('common.loading')}</p>
      return <p className="placeholder">{t('inspect.noFrame')}</p>
    }
    if (k === 'diff') return <DiffTab current={current} frames={frames} query={query} />

    const status = (
      <>
        {m.notReady && !m.meta && <p className="notice info" role="status">{t('inspect.notReady')}</p>}
        {m.error && (
          <p className="notice error" role="alert">
            {t('inspect.metaError', { detail: m.error.message })}{' '}
            <button type="button" onClick={m.retry}>{t('common.retry')}</button>
          </p>
        )}
        {!m.meta && m.loading && <p className="muted" role="status">{t('common.loading')}</p>}
      </>
    )
    return (
      <>
        {status}
        {m.meta && (
          <div className={m.stale ? 'ins-stale' : undefined} aria-busy={m.stale || m.loading}>
            {k === 'meta' ? <MetaTab frame={current} meta={m.meta} /> : <MasksTab meta={m.meta} />}
          </div>
        )}
      </>
    )
  }

  return (
    <div className="ins">
      <div className="ins-head">
        <h2 id={`${id}-title`}>{t('inspect.title')}</h2>
        {current && (
          <span className="ins-frame mono" title={current.id}>
            {current.id}
            {tab !== 'diff' && (m.stale || m.loading) && m.meta && <span className="muted"> · {t('inspect.updating')}</span>}
          </span>
        )}
      </div>
      <div className="ins-tabs" role="tablist" aria-label={t('inspect.tabs')}>
        {TABS.map((k, i) => (
          <button key={k} type="button" role="tab" className="ins-tab"
            id={`${id}-tab-${k}`} aria-controls={`${id}-panel-${k}`}
            aria-selected={tab === k} tabIndex={tab === k ? 0 : -1}
            ref={el => { tabRefs.current[i] = el }}
            onClick={() => setTab(k)} onKeyDown={e => onKeyDown(e, i)}>
            {t(`inspect.tab.${k}`)}
          </button>
        ))}
      </div>
      {TABS.map(k => (
        <div key={k} role="tabpanel" className="ins-panel" id={`${id}-panel-${k}`}
          aria-labelledby={`${id}-tab-${k}`} hidden={tab !== k} tabIndex={0}>
          {tab === k && body(k)}
        </div>
      ))}
    </div>
  )
}
