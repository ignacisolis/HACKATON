// Reproductor: la zona del cielo como video en el tiempo.
//   - qué cuadros entran: sequence.ts (vía useFrames().sequence)
//   - sin parpadeo: preload.ts precarga todos los PNG y la reproducción solo avanza a cuadros cargados
//   - view.t (URL) es el cuadro visible; mientras reproduce se usa un índice local y la URL se
//     escribe al pausar (escribir la URL 12 veces por segundo satura history.replaceState)
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { Detector, ImageLayer } from '../../api/types'
import { useT } from '../../i18n'
import { useFrames } from '../../state/frames'
import { useView } from '../../state/view'
import Pickers from './Pickers'
import { findTarget, useTargets } from '../nav/targets'
import { commonRange } from './contrast'
import { clampIndex, formatDateUTC, formatWavelength, nextPlayable, SPEEDS } from './playback'
import { forgetErrors, loadStatus, usePreload, type LoadStatus } from './preload'
import { referenceWavelength, sequenceStats } from './sequence'
import Stage from './Stage'
import Timeline from './Timeline'
import './player.css'

const FEW_FRAMES = 6
const QUALITY_CLASS = { ok: 'ok', suspect: 'warn', bad: 'bad' } as const

export default function Player() {
  const tr = useT()
  const { view, setView } = useView()
  const { query, coverage, detector, response, frames, sequence, loading, error, reload } = useFrames()
  const n = sequence.length

  const [playingState, setPlaying] = useState(false)
  const playing = playingState && n >= 2
  const [fps, setFps] = useState<number>(4)
  // índice local: solo mientras reproduce o mientras se arrastra la línea de tiempo. En reposo manda
  // la URL (link compartido, otro panel, atrás/adelante).
  const [local, setLocal] = useState<number | null>(null)
  const [epoch, setEpoch] = useState(0)

  // otra posición, detector o banda = otro video: se corta la reproducción (ajuste durante el render,
  // el patrón de React para "resetear estado cuando cambia una prop")
  const ctxKey = `${JSON.stringify(query)}|${detector}|${view.band}`
  const [prevCtx, setPrevCtx] = useState(ctxKey)
  if (prevCtx !== ctxKey) { setPrevCtx(ctxKey); setLocal(null); setPlaying(false) }

  const idx = local ?? view.t
  const i = clampIndex(idx, n)
  const frame = n ? sequence[i] : null

  // ---- URLs y precarga ----------------------------------------------------------------------
  const layer: ImageLayer = view.zodi ? 'image-zodi' : 'image'
  // Contraste común (contrast.ts): solo sobre la imagen sin restar luz zodiacal, que es sobre la que
  // el backend mide display_range. Con ZODI restada el fondo baja y ese rango ya no vale.
  const range = useMemo(
    () => (view.contrast === 'common' && !view.zodi ? commonRange(sequence, view.stretch) : null),
    [sequence, view.contrast, view.zodi, view.stretch],
  )
  const urls = useMemo(
    () => (query ? sequence.map(f => api.frameImageUrl(f, query, {
      stretch: view.stretch, layer, ...(range ? { vmin: range.vmin, vmax: range.vmax } : {}),
    })) : []),
    [sequence, query, view.stretch, layer, range],
  )
  const maskKey = view.mask.join(',')
  const maskUrls = useMemo(
    () => (query && view.mask.length ? sequence.map(f => api.frameImageUrl(f, query, { layer: 'flags', bits: view.mask })) : []),
    [sequence, query, maskKey], // eslint-disable-line react-hooks/exhaustive-deps
  )
  const version = usePreload(urls, i, epoch)
  const maskVersion = usePreload(maskUrls, i, epoch)

  // un cuadro está listo cuando cargó su imagen (y su máscara, si hay; una máscara que falla no frena)
  const frameStatus = useCallback((k: number): LoadStatus | undefined => {
    const s = loadStatus(urls[k])
    if (s !== 'loaded') return s
    if (!maskUrls.length) return 'loaded'
    return loadStatus(maskUrls[k]) ? 'loaded' : undefined
  }, [urls, maskUrls, version, maskVersion]) // eslint-disable-line react-hooks/exhaustive-deps

  const { loadedCount, errorCount } = useMemo(() => {
    let l = 0, e = 0
    for (let k = 0; k < n; k++) { const s = frameStatus(k); if (s === 'loaded') l++; else if (s === 'error') e++ }
    return { loadedCount: l, errorCount: e }
  }, [frameStatus, n])

  // ---- reproducción -------------------------------------------------------------------------
  const statusRef = useRef(frameStatus)
  statusRef.current = frameStatus
  useEffect(() => {
    if (!playing) return
    const id = window.setInterval(
      () => setLocal(cur => nextPlayable(clampIndex(cur ?? 0, n), n, k => statusRef.current(k))),
      1000 / fps,
    )
    return () => window.clearInterval(id)
  }, [playing, fps, n])

  // La secuencia cambia mientras bajan cuadros de IRSA (se insertan por mjd): seguir mostrando el
  // mismo cuadro en su nuevo índice. Solo si el índice era exacto (un t de link compartido que todavía
  // no existe se respeta hasta que la secuencia llegue a ese largo).
  const shown = useRef<{ id: string; exact: boolean } | null>(null)
  useEffect(() => {
    const s = shown.current
    if (!s?.exact || sequence[i]?.id === s.id) return
    const k = sequence.findIndex(f => f.id === s.id)
    if (k < 0) return
    if (local != null) setLocal(k)
    else setView({ t: k })
  }, [sequence]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { shown.current = frame ? { id: frame.id, exact: idx < n } : null })

  // ---- acciones -----------------------------------------------------------------------------
  const commitTimer = useRef<number | undefined>(undefined)
  const pendingT = useRef<number | null>(null)
  useEffect(() => () => window.clearTimeout(commitTimer.current), [])

  /** Ir al cuadro k. Al arrastrar la línea de tiempo la URL se escribe con un pequeño retardo. */
  const goTo = (k: number, debounce = false) => {
    const kk = clampIndex(k, n)
    window.clearTimeout(commitTimer.current)
    setPlaying(false)
    if (debounce) {
      setLocal(kk)
      pendingT.current = kk
      commitTimer.current = window.setTimeout(commitNow, 180)
    } else {
      pendingT.current = null
      setLocal(null); setView({ t: kk }) // juntos: la URL queda en el cuadro visible
    }
  }
  /** Escribe en la URL el cuadro pendiente del arrastre (al soltar o al vencer el retardo). */
  function commitNow() {
    window.clearTimeout(commitTimer.current)
    const k = pendingT.current
    pendingT.current = null
    if (k != null) { setLocal(null); setView({ t: k }) }
  }
  const togglePlay = () => {
    if (playing) { setPlaying(false); setLocal(null); setView({ t: i }); return }
    if (n < 2) return
    setLocal(i)
    setPlaying(true)
  }
  const step = (d: number) => goTo(i + d)

  // teclado: espacio = play/pausa, ←/→ = cuadro anterior/siguiente; no cuando el foco está en un campo
  const keyRef = useRef({ togglePlay, step })
  keyRef.current = { togglePlay, step }
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey || e.ctrlKey || e.metaKey || e.defaultPrevented) return
      const el = e.target as HTMLElement | null
      const tag = el?.tagName ?? ''
      if (['INPUT', 'TEXTAREA', 'SELECT', 'CANVAS'].includes(tag) || el?.isContentEditable) return
      if (e.key === ' ' || e.code === 'Space') {
        if (tag === 'BUTTON' || tag === 'A') return // el botón con foco ya reacciona al espacio
        e.preventDefault(); keyRef.current.togglePlay()
      } else if (e.key === 'ArrowLeft') { e.preventDefault(); keyRef.current.step(-1) }
      else if (e.key === 'ArrowRight') { e.preventDefault(); keyRef.current.step(1) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const retry = () => { forgetErrors(); setEpoch(e => e + 1); reload() }
  const onDetector = (det: Detector) => { setPlaying(false); setLocal(null); setView({ det, band: null, t: 0 }) }
  const onBand = (band: number | null) => { setPlaying(false); setLocal(null); setView({ band, t: 0 }) }

  // ---- avisos -------------------------------------------------------------------------------
  const stats = useMemo(() => sequenceStats(sequence), [sequence])
  const refWl = useMemo(
    () => (view.band == null ? referenceWavelength(frames.filter(f => f.detector === detector)) : null),
    [frames, detector, view.band],
  )
  // coordenadas de catálogo que no coinciden con la posición del objeto en estos datos (WISE 0855:
  // las del enunciado son de ~2010 y caen a ~21 px). Se marcan sobre el recorte para mostrarlo.
  const { list: targets } = useTargets()
  const statement = findTarget(targets, view.target)?.statement ?? null
  const refMarks = statement ? [{ ...statement, label: tr('player.statementLabel') }] : []
  const pending = response?.pending ?? 0
  const total = response?.n_frames ?? 0

  // ---- render -------------------------------------------------------------------------------
  if (!query) return <div className="pl"><h2>{tr('player.title')}</h2><p className="placeholder">{tr('player.noQuery')}</p></div>

  const wlText = frame ? formatWavelength(frame.wavelength_um, frame.bandwidth_um) : ''
  const dateText = frame ? formatDateUTC(frame.date) : ''
  const frameUrl = urls[i] ?? ''
  const maskUrl = maskUrls[i] ?? ''
  const center = response ? { ra: response.query.ra, dec: response.query.dec, size: response.query.size } : null
  const valueText = frame ? `${tr('player.frameOf', { i: i + 1, n })} · ${dateText}` : ''

  return (
    <div className="pl">
      <div className="pl-head">
        <h2>{tr('player.title')}</h2>
        {n > 0 && <span className="pl-count mono muted">{tr('player.frameOf', { i: i + 1, n })}</span>}
      </div>

      <Pickers
        query={query} coverage={coverage} detector={detector} frames={frames} band={view.band}
        onDetector={onDetector} onBand={onBand}
      />

      {error && (
        <div className="notice error pl-row" role="alert">
          <span>{tr('player.error', { code: error.code, message: error.message })}</span>
          <button className="btn" onClick={retry}>{tr('common.retry')}</button>
        </div>
      )}

      {pending > 0 && total > 0 && (
        <div className="notice info pl-progress" role="status">
          <span>{tr('player.downloading', { ready: total - pending, n: total })}</span>
          <progress max={total} value={total - pending} aria-hidden="true" />
        </div>
      )}

      {frame ? (
        <>
          <Stage
            frame={frame}
            url={frameUrl}
            maskUrl={maskUrl}
            center={center}
            pick={view.pick}
            refMarks={refMarks}
            onPick={pick => setView({ pick })}
            waiting={frameStatus(i) === undefined}
            label={tr('player.stageLabel', { date: dateText, det: frame.detector, wl: wlText })}
            title={tr('player.stageTitle')}
            crossLabel={tr('player.crossLabel')}
            pickLabel={tr('player.pickLabel')}
            waitingLabel={tr('player.waitingImage')}
          />

          <div className="pl-meta" aria-live={playing ? 'off' : 'polite'}>
            <span className="mono">{dateText}</span>
            <span className="pl-det mono" style={{ color: `var(--${frame.detector.toLowerCase()})` }}>{frame.detector}</span>
            {frame.band != null && <span className="mono">{tr('player.band')} {frame.band}</span>}
            <span className="mono">λ {wlText}</span>
            <span className="muted" title={tr('player.release')}>{frame.release}</span>
            {frame.quality && (
              <span className={`badge ${QUALITY_CLASS[frame.quality]}`} title={tr(`player.qualityHint.${frame.quality}`)}>
                {tr('player.quality')}: {tr(`player.quality.${frame.quality}`)}
              </span>
            )}
          </div>

          <div className="pl-legend muted">
            <span className="pl-key-cross">{tr('player.legendCross')}</span>
            {view.pick && <span className="pl-key-pick">{tr('player.legendPick')}</span>}
            {view.mask.length > 0 && <span className="pl-key-mask">{tr('player.legendMask', { bits: view.mask.join(', ') })}</span>}
            {refMarks.length > 0 && <span className="pl-key-ref">{tr('player.legendStatement')}</span>}
          </div>

          <div className="pl-controls">
            <button className="btn" onClick={() => step(-1)} disabled={i <= 0} aria-label={tr('player.prev')} title={tr('player.prev')}>⏮</button>
            <button className="btn primary pl-play" onClick={togglePlay} disabled={n < 2}
              aria-label={playing ? tr('player.pause') : tr('player.play')} aria-pressed={playing}>
              {playing ? '⏸' : '▶'} <span className="pl-play-text">{playing ? tr('player.pause') : tr('player.play')}</span>
            </button>
            <button className="btn" onClick={() => step(1)} disabled={i >= n - 1} aria-label={tr('player.next')} title={tr('player.next')}>⏭</button>
            <label className="pl-field pl-inline">
              <span>{tr('player.speed')}</span>
              <select value={fps} onChange={e => setFps(Number(e.currentTarget.value))}>
                {SPEEDS.map(s => <option key={s} value={s}>{tr('player.fps', { n: s })}</option>)}
              </select>
            </label>
            <div className="seg" role="group" aria-label={tr('player.stretch')}>
              {(['asinh', 'linear'] as const).map(s => (
                <button key={s} className={view.stretch === s ? 'on' : ''} aria-pressed={view.stretch === s}
                  onClick={() => setView({ stretch: s })}>{tr(`player.stretch.${s}`)}</button>
              ))}
            </div>
            <div className="seg" role="group" aria-label={tr('player.contrast')} title={tr('player.contrastHint')}>
              {(['common', 'frame'] as const).map(c => (
                <button key={c} className={view.contrast === c ? 'on' : ''} aria-pressed={view.contrast === c}
                  onClick={() => setView({ contrast: c })}>{tr(`player.contrast.${c}`)}</button>
              ))}
            </div>
            <label className="pl-check">
              <input type="checkbox" checked={view.zodi} onChange={e => setView({ zodi: e.currentTarget.checked })} />
              <span>{tr('player.zodi')}</span>
            </label>
          </div>

          <Timeline
            sequence={sequence}
            index={i}
            status={frameStatus}
            onScrub={k => goTo(k, true)}
            onCommit={commitNow}
            label={tr('player.timeline')}
            valueText={valueText}
          />

          <div className="pl-status muted">
            {loadedCount < n && (
              <span className="pl-progress" role="status">
                {tr('player.preloading', { loaded: loadedCount, n })}
                <progress max={n} value={loadedCount} aria-hidden="true" />
              </span>
            )}
            <span className="pl-keys">{tr('player.keys')}</span>
          </div>
        </>
      ) : (
        !error && (
          <p className="placeholder">
            {loading || !response ? tr('player.loading')
              : pending > 0 ? tr('player.waitingFrames', { pending })
              : tr('player.empty')}
          </p>
        )
      )}

      <div className="pl-notices">
        {n > 0 && n < FEW_FRAMES && view.band != null && (
          <div className="notice pl-row">
            <span>{tr('player.fewBand', { n })}</span>
            <button className="btn" onClick={() => onBand(null)}>{tr('player.useAllBands')}</button>
          </div>
        )}
        {n > 0 && n < FEW_FRAMES && view.band == null && pending === 0 && (
          <div className="notice">{tr('player.fewDates', { n: stats.days })}</div>
        )}
        {view.band == null && n > 1 && refWl != null && stats.wlMin != null && stats.wlMax != null && (
          <div className="notice info">
            {tr('player.mixInfo', { ref: refWl.toFixed(3), min: stats.wlMin.toFixed(3), max: stats.wlMax.toFixed(3) })}
          </div>
        )}
        {n > 1 && range && <div className="notice info">{tr('player.contrastOn', { vmin: range.vmin, vmax: range.vmax })}</div>}
        {n > 1 && view.contrast === 'common' && !range && (
          <div className="notice">{tr(view.zodi ? 'player.contrastZodi' : 'player.contrastNone')}</div>
        )}
        {n > 1 && view.contrast === 'frame' && <div className="notice">{tr('player.contrastFrame')}</div>}
        {stats.bad > 0 && <div className="notice">{tr('player.badInSeq', { n: stats.bad })}</div>}
        {errorCount > 0 && <div className="notice">{tr('player.imgErrors', { n: errorCount })}</div>}
        {view.target === 'wise_0855' && <div className="notice info">{tr('player.wise0855')}</div>}
        {view.target === 'eps_ind_b' && <div className="notice info">{tr('player.epsIndB')}</div>}
      </div>
    </div>
  )
}
