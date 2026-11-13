// Pestaña Resta (C5): A = cuadro actual del reproductor, B = referencia guardada en view.diff.
// La comparabilidad del cliente es solo una ayuda para elegir; antes de mostrar la imagen se le
// pregunta al backend (api.diffCheck): 422 = no comparables, 404/501 = /api/diff todavía no existe.
import { useEffect, useId, useMemo, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { Frame, SkyQuery } from '../../api/types'
import { useT } from '../../i18n'
import { useView } from '../../state/view'
import { findTarget, useTargets } from '../nav/targets'
import {
  candidates, classifyDiff, compareHint, defaultReference, fmtDateUtc, fmtNum,
  type CompareHint, type CompareLevel, type DiffStatus, type Lang,
} from './logic'
import { SkyImage, type Marker } from './parts'
import type { T } from './text'

const LEVELS: CompareLevel[] = ['likely', 'unknown', 'unlikely']
/** Espera antes de consultar: si el video está corriendo, no se consulta cada cuadro. */
const CHECK_DEBOUNCE_MS = 250

type Mode = 'diff' | 'side'
type Checked = DiffStatus | { kind: 'checking' }

function optionLabel(t: T, f: Frame, dt: number, lang: Lang): string {
  return t('inspect.diff.option', {
    date: fmtDateUtc(f.date).slice(0, 16),
    lambda: f.wavelength_um != null ? `${fmtNum(f.wavelength_um, 4, lang)} µm` : 'λ ?',
    dt: fmtNum(dt, 1, lang),
  })
}

function hintText(t: T, h: CompareHint, lang: Lang): string {
  const vars = { dlam: h.dlam != null ? fmtNum(h.dlam, 4, lang) : '?', tol: h.tol != null ? fmtNum(h.tol, 4, lang) : '?' }
  return t(`inspect.diff.hint.${h.reason}`, vars)
}

function StatusNotice({ s, onRetry }: { s: Checked; onRetry: () => void }) {
  const t = useT()
  switch (s.kind) {
    case 'ok': return null
    case 'checking': return <p className="notice info" role="status">{t('inspect.diff.checking')}</p>
    case 'not_comparable': return <p className="notice error" role="alert">{t('inspect.diff.notComparable', { detail: s.detail })}</p>
    case 'pending_backend': return <p className="notice" role="status">{t('inspect.diff.pending')}</p>
    case 'network': return (
      <p className="notice error" role="alert">
        {t('inspect.diff.network', { detail: s.detail })} <button type="button" onClick={onRetry}>{t('common.retry')}</button>
      </p>
    )
    case 'error': return (
      <p className="notice error" role="alert">
        {t('inspect.diff.error', { status: s.status, detail: s.detail })} <button type="button" onClick={onRetry}>{t('common.retry')}</button>
      </p>
    )
  }
}

export default function DiffTab({ current: videoFrame, frames, query }: { current: Frame; frames: Frame[]; query: SkyQuery }) {
  const t = useT()
  const { view, setView } = useView()
  const { list: targets } = useTargets()
  const target = findTarget(targets, view.target)
  const best = target?.bestPair ?? null
  const motion = target?.motion ?? null
  const lang = view.lang
  const selId = useId()
  const [mode, setMode] = useState<Mode>('diff')
  const [nonce, setNonce] = useState(0)
  const [checked, setChecked] = useState<{ key: string; s: Checked } | null>(null)

  const byId = useMemo(() => new Map(frames.map(f => [f.id, f])), [frames])
  // A fijado (view.diffA, p. ej. el mejor par del backend): no sigue al video. Si todavía no está entre
  // los cuadros (se está cargando otro detector), A sigue siendo el cuadro del video.
  const pinned = view.diffA ? byId.get(view.diffA) ?? null : null
  const current = pinned ?? videoFrame
  const onBest = best != null && view.diffA === best.a && view.diff === best.b
  const applyBest = () => { if (best) setView({ det: best.detector, band: null, diffA: best.a, diff: best.b }) }
  const loadingBest = best != null && view.diffA === best.a && !pinned
  const cands = useMemo(() => candidates(current, frames), [current, frames])
  const proposed = useMemo(() => defaultReference(current, frames), [current, frames])
  const chosen = view.diff ? byId.get(view.diff) ?? null : null
  const B = chosen ?? proposed
  const same = B != null && B.id === current.id

  // Si no hay B guardado (o ya no está entre los cuadros), se guarda el sugerido: la URL refleja lo que se ve.
  useEffect(() => {
    // con A fijado (mejor par) no se pisa B: mientras carga el otro detector B todavía no está en la lista
    if (!view.diffA && !chosen && proposed && view.diff !== proposed.id) setView({ diff: proposed.id })
  }, [chosen, proposed?.id, view.diffA]) // eslint-disable-line react-hooks/exhaustive-deps

  const qKey = JSON.stringify(query)
  const key = B && !same ? `${current.id}|${B.id}|${qKey}|${nonce}` : null
  useEffect(() => {
    if (!key || !B) return
    const ac = new AbortController()
    const timer = window.setTimeout(() => {
      api.diffCheck(current, B, query, ac.signal)
        .then(e => setChecked({ key, s: classifyDiff(e) }))
        .catch(e => {
          if ((e as Error).name === 'AbortError') return
          setChecked({ key, s: classifyDiff(new ApiError(0, { error: 'network', detail: String(e) })) })
        })
    }, CHECK_DEBOUNCE_MS)
    return () => { window.clearTimeout(timer); ac.abort() }
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps

  const status: Checked = key && checked?.key === key ? checked.s : { kind: 'checking' }
  const nCands = cands.likely.length + cands.unknown.length + cands.unlikely.length
  const hint = B && !same ? compareHint(current, B) : null
  const markers: Marker[] = [{ xy: current.target_xy, kind: 'a' }, ...(B ? [{ xy: B.target_xy, kind: 'b' as const }] : [])]
  const diffUrl = B && !same ? api.diffImageUrl(current, B, query) : ''
  const diffAlt = B ? t('inspect.diff.alt', { a: current.id, b: B.id }) : ''

  const diffFigure = status.kind === 'ok' && diffUrl
    ? <SkyImage key={diffUrl} src={diffUrl} alt={diffAlt} markers={markers} caption={mode === 'side' ? 'A − B' : undefined} />
    : mode === 'side' ? <figure className="ins-fig"><div className="ins-img ins-img-empty muted">A − B</div><figcaption>A − B</figcaption></figure> : null

  return (
    <div className="ins-diff">
      <p className="ins-lead">{t('inspect.diff.intro')}</p>

      {best && (
        <div className={`ins-best ${onBest ? 'on' : ''}`}>
          <p className="ins-best-head">
            <strong>{t('inspect.diff.best.title')}</strong>
            {motion && <span className={`badge ${motion.claim === 'confirmado' ? 'ok' : motion.claim === 'indicio' ? 'warn' : ''}`}>
              {t(`inspect.diff.best.claim.${motion.claim === 'confirmado' ? 'confirmed' : motion.claim === 'indicio' ? 'hint' : 'none'}`)}
              {' · '}{t('inspect.diff.best.detectors', { k: motion.detectors_consistent, n: motion.detectors_tested })}
            </span>}
          </p>
          <p className="muted mono">
            {t('inspect.diff.best.detail', {
              det: best.detector, dt: fmtNum(best.dt_days, 0, lang),
              snr: fmtNum(Math.min(best.pos_snr, best.neg_snr), 1, lang),
            })}
          </p>
          {!onBest && <button type="button" className="btn primary" onClick={applyBest}>{t('inspect.diff.best.use')}</button>}
          {loadingBest && <p className="notice info" role="status">{t('inspect.diff.best.loading')}</p>}
          {pinned && (
            <p className="muted">
              {t('inspect.diff.best.pinned')}{' '}
              <button type="button" className="ins-suggest" onClick={() => setView({ diffA: null })}>{t('inspect.diff.best.unpin')}</button>
            </p>
          )}
          {motion?.claim === 'no' && <p className="muted">{t('inspect.diff.best.noMotion')}</p>}
        </div>
      )}

      <dl className="ins-dl ins-ab">
        <dt>{t('inspect.diff.a')}</dt>
        <dd className="mono">
          {fmtDateUtc(current.date).slice(0, 16)} · {current.wavelength_um != null ? `${fmtNum(current.wavelength_um, 4, lang)} µm` : 'λ ?'}
        </dd>
      </dl>

      {nCands === 0 ? <p className="muted">{t('inspect.diff.noCandidates')}</p> : (
        <div className="ins-field">
          <label htmlFor={selId}>{t('inspect.diff.pick')}</label>
          <select id={selId} className="ins-select" value={B && !same ? B.id : ''}
            onChange={e => setView({ diff: e.target.value || null })}>
            {(!B || same) && <option value="" disabled>—</option>}
            {LEVELS.map(level => cands[level].length > 0 && (
              <optgroup key={level} label={t(`inspect.diff.group.${level}`)}>
                {cands[level].map(c => (
                  <option key={c.frame.id} value={c.frame.id}>
                    {optionLabel(t, c.frame, c.dt, lang)}{c.frame.id === proposed?.id ? ` · ${t('inspect.diff.suggested')}` : ''}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          {hint && (
            <p className={`ins-hint ins-cmp ${hint.level}`}>
              {B && <span className="mono">{t('inspect.diff.dt', { dt: fmtNum(Math.abs(B.mjd - current.mjd), 1, lang) })}</span>}{' · '}
              {hintText(t, hint, lang)}
            </p>
          )}
          {proposed && B?.id !== proposed.id && (
            <button type="button" className="ins-suggest" onClick={() => setView({ diff: proposed.id })} title={t('inspect.diff.suggestHint')}>
              {t('inspect.diff.suggest')}
            </button>
          )}
        </div>
      )}

      {same && <p className="notice">{t('inspect.diff.same')}</p>}

      {B && !same && (
        <>
          <div className="ins-actions">
            <span className="muted">{t('inspect.diff.mode')}</span>
            <div className="seg" role="group" aria-label={t('inspect.diff.mode')}>
              {(['diff', 'side'] as const).map(m => (
                <button key={m} type="button" className={mode === m ? 'on' : ''} aria-pressed={mode === m} onClick={() => setMode(m)}>
                  {t(`inspect.diff.mode.${m}`)}
                </button>
              ))}
            </div>
          </div>

          <StatusNotice s={status} onRetry={() => setNonce(n => n + 1)} />

          {mode === 'diff' ? diffFigure : (
            <div className="ins-side">
              <SkyImage key={`a-${current.id}`} src={api.frameImageUrl(current, query, { stretch: view.stretch })}
                alt={t('inspect.diff.altFrame', { id: current.id })} markers={[markers[0]]} caption="A" />
              <SkyImage key={`b-${B.id}`} src={api.frameImageUrl(B, query, { stretch: view.stretch })}
                alt={t('inspect.diff.altFrame', { id: B.id })} markers={markers.slice(1)} caption="B" />
              {diffFigure}
            </div>
          )}

          <p className="ins-legend" aria-hidden="true">
            <span><span className="ins-mark a" /> {t('inspect.diff.legendA')}</span>
            <span><span className="ins-mark b" /> {t('inspect.diff.legendB')}</span>
          </p>
        </>
      )}

      <details className="ins-how" open>
        <summary>{t('inspect.diff.howTitle')}</summary>
        <p>{t('inspect.diff.how')}</p>
        <p className="muted">{t('inspect.diff.howSmall')}</p>
      </details>
    </div>
  )
}
