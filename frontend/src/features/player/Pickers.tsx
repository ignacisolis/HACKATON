// Selector de detector y de banda (C3). Una banda se elige SIEMPRE dentro de un detector: las bandas
// se solapan en las costuras entre detectores, así que elegir solo por λ mezclaría dos.
import { useEffect, useMemo, useReducer } from 'react'
import { api } from '../../api/client'
import type { CoverageResponse, Detector, Frame, SkyQuery } from '../../api/types'
import { DETECTORS } from '../../api/types'
import { useT } from '../../i18n'
import { detectorCoverage, NOMINAL_RANGE_UM } from './detectors'
import { bandOptions, wavelengthRange, type BandOption } from './sequence'

// Bandas por (consulta, detector). Con banda fija, useFrames().frames solo trae esa banda: para
// ofrecer las demás se recuerdan las vistas en modo "todas", o se piden una vez por la capa de API.
const bandCache = new Map<string, BandOption[]>()

function useBandOptions(query: SkyQuery | null, detector: Detector | null, frames: Frame[], band: number | null): BandOption[] {
  const [, force] = useReducer((x: number) => x + 1, 0)
  const key = query && detector ? `${JSON.stringify(query)}|${detector}` : ''
  // frames puede traer por un render los del detector anterior: se filtra por el actual
  const own = useMemo(() => frames.filter(f => f.detector === detector), [frames, detector])
  const live = useMemo(() => (band == null ? bandOptions(own) : null), [own, band])

  useEffect(() => { if (key && live?.length) bandCache.set(key, live) }, [key, live])

  useEffect(() => {
    if (band == null || !key || !query || !detector || bandCache.has(key)) return
    const ac = new AbortController()
    api.frames(query, { detector }, ac.signal)
      .then(r => { bandCache.set(key, bandOptions(r.frames)); force() })
      .catch(() => { /* sin la lista, se ofrece al menos la banda actual */ })
    return () => ac.abort()
  }, [band, key]) // eslint-disable-line react-hooks/exhaustive-deps

  const opts = live ?? bandCache.get(key) ?? []
  if (band != null && !opts.some(o => o.band === band)) {
    const fromFrames = bandOptions(own).find(o => o.band === band)
    return [...opts, fromFrames ?? { band, wavelength_um: NaN, bandwidth_um: null, count: own.length }].sort((a, b) => a.band - b.band)
  }
  return opts
}

const fmtRange = ([a, b]: [number, number]) => `${a.toFixed(2)}–${b.toFixed(2)}`

interface Props {
  query: SkyQuery | null
  coverage: CoverageResponse | null
  detector: Detector | null
  frames: Frame[]
  band: number | null
  onDetector: (d: Detector) => void
  onBand: (b: number | null) => void
}

export default function Pickers({ query, coverage, detector, frames, band, onDetector, onBand }: Props) {
  const tr = useT()
  const opts = useBandOptions(query, detector, frames, band)
  // rango medido del detector activo (solo en modo "todas las bandas" representa al detector entero)
  const measured = useMemo(
    () => (band == null ? wavelengthRange(frames.filter(f => f.detector === detector)) : null),
    [frames, detector, band],
  )

  return (
    <div className="pl-pickers">
      <label className="pl-field">
        <span>{tr('player.detector')}</span>
        <select
          value={detector ?? ''}
          disabled={!detector}
          onChange={e => onDetector(e.currentTarget.value as Detector)}
        >
          {!detector && <option value="">{tr('common.loading')}</option>}
          {DETECTORS.map(d => {
            const cov = detectorCoverage(coverage, d)
            const wl = fmtRange(d === detector && measured ? measured : NOMINAL_RANGE_UM[d])
            const text = cov
              ? tr('player.detectorOption', { det: d, wl, dates: cov.dates, frames: cov.frames })
              : tr('player.detectorOptionNoCov', { det: d, wl })
            return <option key={d} value={d} disabled={cov != null && cov.frames === 0}>{text}</option>
          })}
        </select>
      </label>
      <label className="pl-field">
        <span>{tr('player.band')}</span>
        <select
          value={band == null ? '' : String(band)}
          disabled={!detector}
          onChange={e => onBand(e.currentTarget.value === '' ? null : Number(e.currentTarget.value))}
          aria-describedby="pl-band-hint"
        >
          <option value="">{tr('player.allBands', { det: detector ?? '—' })}</option>
          {opts.map(o => (
            <option key={o.band} value={o.band}>
              {tr('player.bandOption', { band: o.band, wl: Number.isFinite(o.wavelength_um) ? o.wavelength_um.toFixed(3) : '—', n: o.count })}
            </option>
          ))}
        </select>
      </label>
      <p id="pl-band-hint" className="pl-hint muted">{tr('player.bandHint')}</p>
    </div>
  )
}
