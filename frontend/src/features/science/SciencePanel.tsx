// Panel de ciencia: espectro instantáneo (C7) y curva de luz de la banda elegida.
// Posición: el punto clickeado en la imagen (view.pick) o, si no hay, el objetivo/centro de la vista.
// Click en un punto del espectro → setView({det, band, t:0}): el video se filtra a esa banda y abajo
// aparece su curva de luz. Con el backend sin la función de ciencia (501) se avisa; nunca se inventan
// datos fuera del modo fixtures.
import { useMemo, useState } from 'react'
import { api, USE_FIXTURES } from '../../api/client'
import type { Detector, SkyQuery, SpectrumPoint, TargetKey } from '../../api/types'
import { useT } from '../../i18n'
import { formatDec, formatRA } from '../../lib/sky'
import { useFrames } from '../../state/frames'
import { skyQueryOf, useView } from '../../state/view'
import { formatNum } from './chart'
import { useResource, type Resource } from './hooks'
import LightCurveChart from './LightCurveChart'
import SpectrumChart from './SpectrumChart'
import {
  classifyError, detColor, detectorRanges, isSelected, lightCurveRows, plottable, pointKey, type FluxScale,
} from './spectrum'
import './science.css'

/** Nombres cortos de los objetivos de la demo, solo para el rótulo de posición. */
const TARGET_NAMES: Record<TargetKey, string> = {
  eps_ind_b: 'Epsilon Indi B', wise_0855: 'WISE 0855−0714', rw_aur: 'RW Aurigae A', r_dra: 'R Draconis',
}

type T = ReturnType<typeof useT>

/** Cargando / error / 501 de un recurso. No dibuja nada cuando hay datos. */
function ResourceState({ res, what, height }: { res: Resource<unknown>; what: 'spectrum' | 'lc'; height: number }) {
  const t = useT()
  if (res.status === 'loading') {
    return (
      <div className="sci-skel" style={{ height }} aria-busy="true" role="status">
        <span className="sr-only">{t('common.loading')}</span>
      </div>
    )
  }
  if (res.status !== 'error') return null
  const kind = classifyError(res.error)
  if (kind === 'not_implemented') {
    return <p className="notice info sci-501" role="status">{t(`science.${what}.notImplemented`)}</p>
  }
  const detail = res.error instanceof Error ? res.error.message : String(res.error)
  return (
    <div className="notice error sci-errbox" role="alert">
      <span>{t(kind === 'network' ? 'science.error.network' : `science.${what}.error`, { detail })}</span>
      <button className="btn sci-small" onClick={res.reload}>{t('common.retry')}</button>
    </div>
  )
}

function PositionBar({ t }: { t: T }) {
  const { view, setView } = useView()
  let label: string
  if (view.pick) label = t('science.pos.pick', { ra: formatRA(view.pick.ra), dec: formatDec(view.pick.dec) })
  else if (view.target) label = t('science.pos.target', { name: TARGET_NAMES[view.target] ?? view.target })
  else if (view.ra != null && view.dec != null) label = t('science.pos.center', { ra: formatRA(view.ra), dec: formatDec(view.dec) })
  else label = t('science.pos.none')
  return (
    <div className="sci-pos">
      <span className={`badge ${view.pick ? 'warn' : 'ok'}`}>{t(view.pick ? 'science.pos.pickBadge' : view.target ? 'science.pos.targetBadge' : 'science.pos.centerBadge')}</span>
      <span className="sci-pos-text">{label}</span>
      {view.pick && (
        <button className="btn sci-small" onClick={() => setView({ pick: null })}>
          {t(view.target ? 'science.pos.resetTarget' : 'science.pos.resetCenter')}
        </button>
      )}
    </div>
  )
}

function Legend({ points, t }: { points: SpectrumPoint[]; t: T }) {
  const dets = detectorRanges(points)
  return (
    <ul className="sci-legend" aria-label={t('science.legend')}>
      {dets.map(d => (
        <li key={d.detector}>
          <span className="sci-swatch" style={{ background: detColor(d.detector) }} />{d.detector}
          <span className="muted">{d.min.toFixed(2)}–{d.max.toFixed(2)} µm</span>
        </li>
      ))}
      <li><svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="3.5" className="sci-leg-dot" /></svg>{t('science.quality.ok')}</li>
      <li><svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="3.5" className="sci-leg-hollow" /></svg>{t('science.quality.suspect')}</li>
      <li><svg width="12" height="12" aria-hidden="true"><path d="M3 3L9 9M3 9L9 3" className="sci-leg-x" /></svg>{t('science.quality.bad')}</li>
      <li className="muted">{t('science.legend.bars')}</li>
    </ul>
  )
}

function DataTable({ points, band, det, onSelect, t }: {
  points: SpectrumPoint[]; band: number | null; det: Detector | null; onSelect: (p: SpectrumPoint) => void; t: T
}) {
  return (
    <details className="sci-table">
      <summary>{t('science.table', { n: points.length })}</summary>
      <div className="sci-tablewrap">
        <table>
          <thead>
            <tr>
              <th>{t('science.col.band')}</th><th>{t('science.col.det')}</th><th>λ (µm)</th><th>Δλ (µm)</th>
              <th>{t('science.col.flux')}</th><th>{t('science.col.epochs')}</th><th>{t('science.col.flagged')}</th>
              <th>{t('science.col.quality')}</th><th><span className="sr-only">{t('science.table.choose')}</span></th>
            </tr>
          </thead>
          <tbody>
            {points.map(p => (
              <tr key={pointKey(p)} className={isSelected(p, band, det) ? 'sel' : undefined}>
                <td>{p.band}</td><td style={{ color: detColor(p.detector) }}>{p.detector}</td>
                <td className="mono">{p.wavelength_um.toFixed(4)}</td><td className="mono">{p.bandwidth_um.toFixed(4)}</td>
                <td className="mono">{formatNum(p.flux)} ± {formatNum(p.flux_err, 2)}</td>
                <td className="mono">{p.n_epochs}</td><td className="mono">{(p.flagged_fraction * 100).toFixed(0)} %</td>
                <td>{t(`science.quality.${p.quality}`)}</td>
                <td>
                  <button className="btn sci-small" onClick={() => onSelect(p)}
                    aria-label={t('science.table.chooseBand', { band: p.band, det: p.detector })}>{t('science.table.choose')}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

export default function SciencePanel() {
  const t = useT()
  const { view, setView } = useView()
  const { current } = useFrames()

  // posición del espectro: el punto clickeado gana sobre el objetivo/centro
  const query: SkyQuery | null = useMemo(
    () => (view.pick ? { ra: view.pick.ra, dec: view.pick.dec, size: view.fov } : skyQueryOf(view)),
    [view.pick?.ra, view.pick?.dec, view.target, view.ra, view.dec, view.fov], // eslint-disable-line react-hooks/exhaustive-deps
  )
  const qKey = query ? JSON.stringify(query) : null
  const spec = useResource(qKey, s => api.spectrum(query!, s))

  const [scale, setScale] = useState<FluxScale>('linear')
  const [showBad, setShowBad] = useState(false)
  const [showRefs, setShowRefs] = useState(false)

  const all = useMemo(() => spec.data?.points ?? [], [spec.data])
  const sorted = useMemo(() => [...all].sort((a, b) => a.wavelength_um - b.wavelength_um), [all])
  const { shown, hiddenBad, hiddenNonPositive } = useMemo(() => plottable(all, { showBad, scale }), [all, showBad, scale])
  const nBad = all.filter(p => p.quality === 'bad').length
  const unit = all[0]?.unit ?? 'MJy/sr'
  const select = (p: SpectrumPoint) => setView({ det: p.detector, band: p.band, t: 0 })

  // curva de luz de la banda elegida (en el espectro o fijada en el reproductor / la URL)
  const band = view.band
  const lcKey = query && band != null ? `${qKey}|${band}` : null
  const lc = useResource(lcKey, s => api.lightcurve(query!, band!, s))
  const lcRows = useMemo(() => (lc.data ? lightCurveRows(lc.data) : []), [lc.data])
  const selPoint = all.find(p => isSelected(p, band, view.det)) ?? null
  const lcColor = detColor(selPoint?.detector ?? view.det ?? 'D1')
  const span = lcRows.length > 1 ? Math.round(lcRows[lcRows.length - 1].mjd - lcRows[0].mjd) : 0
  const sd = spec.data

  return (
    <section className="sci" aria-labelledby="sci-h">
      <div className="sci-head">
        <h2 id="sci-h">{t('science.title')}</h2>
        <PositionBar t={t} />
      </div>

      {USE_FIXTURES && <p className="notice sci-demo" role="note">{t('science.demo')}</p>}
      {view.target === 'r_dra' && !view.pick && <p className="notice" role="note">{t('science.saturated')}</p>}

      {!query ? <p className="notice info">{t('science.pos.none')}</p> : (
        <>
          {/* ---------------- espectro ---------------- */}
          <div className="sci-block">
            <div className="sci-blockhead">
              <h3>{t('science.spectrum.title')}</h3>
              <div className="sci-controls">
                <div className="seg" role="group" aria-label={t('science.scale')}>
                  {(['linear', 'log'] as const).map(s => (
                    <button key={s} className={scale === s ? 'on' : ''} aria-pressed={scale === s}
                      onClick={() => setScale(s)}>{t(`science.scale.${s}`)}</button>
                  ))}
                </div>
                <label className="sci-check">
                  <input type="checkbox" checked={showRefs} onChange={e => setShowRefs(e.target.checked)} />
                  {t('science.refs')}
                </label>
                {nBad > 0 && (
                  <label className="sci-check">
                    <input type="checkbox" checked={showBad} onChange={e => setShowBad(e.target.checked)} />
                    {t('science.showBad', { n: nBad })}
                  </label>
                )}
              </div>
            </div>

            <ResourceState res={spec} what="spectrum" height={300} />

            {sd && (
              <>
                <div className="sci-meta">
                  <span className="badge">{t('science.meta.points', { n: sd.n_points })}</span>
                  <span className="badge" title={t('science.meta.epochsHint')}>{t('science.meta.epochs', { n: sd.n_epochs_used })}</span>
                  <span className="badge">{t('science.meta.aperture', { n: sd.aperture_px })}</span>
                  <span className={`badge ${sd.mask_purpose === 'photometry' ? 'ok' : 'bad'}`}>
                    {t('science.meta.mask', { purpose: sd.mask_purpose })}
                  </span>
                </div>
                {sd.mask_purpose !== 'photometry' && <p className="notice error">{t('science.meta.maskWarn')}</p>}

                {shown.length === 0 ? <p className="notice info">{t('science.spectrum.empty')}</p> : (
                  <SpectrumChart points={shown} unit={unit} scale={scale} showRefs={showRefs}
                    band={band} det={view.det} onSelect={select} />
                )}

                {(hiddenBad > 0 || hiddenNonPositive > 0) && (
                  <p className="sci-foot muted">
                    {hiddenBad > 0 && t('science.hidden.bad', { n: hiddenBad })}
                    {hiddenBad > 0 && hiddenNonPositive > 0 && ' · '}
                    {hiddenNonPositive > 0 && t('science.hidden.nonPositive', { n: hiddenNonPositive })}
                  </p>
                )}
                {showRefs && <p className="sci-foot sci-refnote">{t('science.refs.note')}</p>}
                <Legend points={all} t={t} />
                <p className="sci-foot muted">{t('science.spectrum.hint')}</p>
                <DataTable points={sorted} band={band} det={view.det} onSelect={select} t={t} />
              </>
            )}
          </div>

          {/* ---------------- curva de luz ---------------- */}
          <div className="sci-block">
            <div className="sci-blockhead">
              <h3>{t('science.lc.title')}</h3>
              {band != null && (
                <div className="sci-controls">
                  <span className="sci-bandtag" style={{ borderColor: lcColor }}>
                    {selPoint
                      ? t('science.lc.bandFull', { band, det: selPoint.detector, wl: selPoint.wavelength_um.toFixed(3) })
                      : t('science.lc.band', { band })}
                  </span>
                  <button className="btn sci-small" onClick={() => setView({ band: null, t: 0 })}>{t('science.lc.clear')}</button>
                </div>
              )}
            </div>

            {band == null ? <p className="notice info">{t('science.lc.pick')}</p> : (
              <>
                <ResourceState res={lc} what="lc" height={220} />
                {lc.status === 'ok' && (lcRows.length === 0 ? <p className="notice info">{t('science.lc.empty')}</p> : (
                  <>
                    <LightCurveChart rows={lcRows} unit={unit} color={lcColor} band={band} lang={view.lang}
                      currentMjd={current?.mjd ?? null} />
                    <p className="sci-foot muted">
                      {t('science.lc.span', { n: lcRows.length, days: span })}
                      {current?.mjd != null && ` · ${t('science.lc.currentHint')}`}
                    </p>
                  </>
                ))}
              </>
            )}
          </div>
        </>
      )}
    </section>
  )
}
