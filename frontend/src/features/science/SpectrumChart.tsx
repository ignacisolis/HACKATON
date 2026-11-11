// Espectro instantáneo en SVG a mano. Eje x: λ en µm, log. Eje y: flujo, lineal o log.
// Cada punto lleva barra de error vertical y barra horizontal del ancho de banda: sin el ancho, las
// bandas angostas de D5–D6 (R≈110–130) y las anchas de D1–D4 (R≈40) dibujan una forma falsa.
import { useId, useMemo, useRef } from 'react'
import type { Detector, SpectrumPoint } from '../../api/types'
import { useT } from '../../i18n'
import { clamp, formatNum, linearScale, logScale, logTicks, niceLinearTicks, stackLabels } from './chart'
import { useChartCursor, useWidth } from './hooks'
import { MOLECULAR_REFS, WL_DOMAIN, detColor, detectorRanges, fluxDomain, isSelected, pointKey, type FluxScale } from './spectrum'

interface Props {
  /** puntos ya filtrados (plottable) y ordenados por λ */
  points: SpectrumPoint[]
  unit: string
  scale: FluxScale
  showRefs: boolean
  band: number | null
  det: Detector | null
  onSelect: (p: SpectrumPoint) => void
}

export default function SpectrumChart({ points, unit, scale, showRefs, band, det, onSelect }: Props) {
  const t = useT()
  const uid = useId()
  const wrap = useRef<HTMLDivElement>(null)
  const width = Math.max(240, useWidth(wrap))
  const narrow = width < 480
  const H = narrow ? 250 : 300
  const M = { l: narrow ? 42 : 52, r: 10, t: 20, b: 38 }
  const plotB = H - M.b

  const x = logScale(WL_DOMAIN, [M.l, width - M.r])
  const dom = fluxDomain(points, scale) ?? (scale === 'log' ? [0.1, 1] as [number, number] : [0, 1] as [number, number])
  const y = (scale === 'log' ? logScale : linearScale)(dom, [plotB, M.t])
  const xTicks = logTicks(WL_DOMAIN[0], WL_DOMAIN[1], narrow ? 6 : 9)
  const yTicks = scale === 'log' ? logTicks(dom[0], dom[1], narrow ? 4 : 6) : niceLinearTicks(dom[0], dom[1], narrow ? 4 : 6)
  const ranges = useMemo(() => detectorRanges(points), [points])
  const pos = points.map(p => ({ x: x(p.wavelength_um), y: y(p.flux) }))
  const selIdx = points.findIndex(p => isSelected(p, band, det))
  const { active, handlers } = useChartCursor(pos, {
    maxDist: narrow ? 30 : 22, start: Math.max(0, selIdx), onPick: i => onSelect(points[i]),
  })
  const yClamp = (v: number) => clamp(isFinite(v) ? v : plotB, M.t, plotB)

  // referencias moleculares (referencia general, aproximada): etiquetas apiladas para que no se pisen
  const refs = showRefs ? MOLECULAR_REFS.map(r => ({ ...r, text: `~${r.ice ? t('science.refs.ice') : r.label}`, px: x(r.um) })) : []
  const refRows = stackLabels(refs.map(r => r.px + 2), refs.map(r => r.text.length * 6 + 6))

  const a = active != null ? points[active] : null
  const titleId = `${uid}-t`, descId = `${uid}-d`

  return (
    <div className="sci-chart" ref={wrap}>
      <svg width={width} height={H} viewBox={`0 0 ${width} ${H}`} className="sci-svg" role="img"
        aria-labelledby={`${titleId} ${descId}`} tabIndex={0} {...handlers}>
        <title id={titleId}>{t('science.spectrum.title')}</title>
        <desc id={descId}>{t('science.spectrum.desc', { n: points.length, unit })}</desc>

        {/* tramo de cada detector: deja ver las costuras */}
        {ranges.map(r => (
          <g key={r.detector}>
            <rect x={x(r.min)} y={M.t} width={Math.max(1, x(r.max) - x(r.min))} height={plotB - M.t}
              fill={detColor(r.detector)} className="sci-detband" />
            <text x={(x(r.min) + x(r.max)) / 2} y={M.t - 6} textAnchor="middle" className="sci-detlabel"
              fill={detColor(r.detector)}>{r.detector}</text>
          </g>
        ))}

        {/* grilla y ejes */}
        {yTicks.map(v => (
          <g key={`y${v}`}>
            <line x1={M.l} x2={width - M.r} y1={y(v)} y2={y(v)} className="sci-grid" />
            <text x={M.l - 5} y={y(v)} dy="0.32em" textAnchor="end" className="sci-tick">{formatNum(v)}</text>
          </g>
        ))}
        {xTicks.map(v => (
          <g key={`x${v}`}>
            <line x1={x(v)} x2={x(v)} y1={plotB} y2={plotB + 4} className="sci-axis" />
            <text x={x(v)} y={plotB + 15} textAnchor="middle" className="sci-tick">{formatNum(v)}</text>
          </g>
        ))}
        <line x1={M.l} x2={width - M.r} y1={plotB} y2={plotB} className="sci-axis" />
        <line x1={M.l} x2={M.l} y1={M.t} y2={plotB} className="sci-axis" />
        <text x={(M.l + width - M.r) / 2} y={H - 4} textAnchor="middle" className="sci-axislabel">{t('science.axis.wavelength')}</text>
        <text transform={`translate(11 ${(M.t + plotB) / 2}) rotate(-90)`} textAnchor="middle" className="sci-axislabel">
          {t('science.axis.flux', { unit })}{scale === 'log' ? ' · log' : ''}
        </text>

        {refs.map((r, i) => (
          <g key={r.id} className="sci-ref">
            <line x1={r.px} x2={r.px} y1={M.t} y2={plotB} />
            <text x={r.px + 2} y={M.t + 10 + refRows[i] * 11}>{r.text}</text>
          </g>
        ))}

        {/* banda elegida */}
        {points.map((p, i) => isSelected(p, band, det) && (
          <line key={`sel${pointKey(p)}`} x1={pos[i].x} x2={pos[i].x} y1={M.t} y2={plotB} className="sci-selline" />
        ))}

        {points.map((p, i) => {
          const cx = pos[i].x, cy = yClamp(pos[i].y)
          const half = p.bandwidth_um / 2
          return (
            <g key={pointKey(p)} className={`sci-pt q-${p.quality}`} style={{ color: detColor(p.detector) }}>
              <line x1={x(p.wavelength_um - half)} x2={x(p.wavelength_um + half)} y1={cy} y2={cy} className="sci-bw" />
              <line x1={cx} x2={cx} y1={yClamp(y(p.flux - p.flux_err))} y2={yClamp(y(p.flux + p.flux_err))} className="sci-err" />
              {p.quality === 'bad'
                ? <path d={`M${cx - 3} ${cy - 3}L${cx + 3} ${cy + 3}M${cx - 3} ${cy + 3}L${cx + 3} ${cy - 3}`} className="sci-x" />
                : <circle cx={cx} cy={cy} r={narrow ? 2.6 : 3.2} className={p.quality === 'suspect' ? 'sci-hollow' : 'sci-dot'} />}
              {isSelected(p, band, det) && <circle cx={cx} cy={cy} r={7} className="sci-selring" />}
              {i === active && <circle cx={cx} cy={cy} r={6} className="sci-activering" />}
            </g>
          )
        })}
      </svg>

      {a && active != null && (
        <div className="sci-tip" role="status"
          style={pos[active].x > width / 2 ? { left: M.l + 6, top: M.t + 4 } : { right: M.r + 6, top: M.t + 4 }}>
          <strong>{t('science.tip.band', { band: a.band, det: a.detector })}</strong>
          <span>{t('science.tip.wl', { wl: a.wavelength_um.toFixed(3), bw: a.bandwidth_um.toFixed(4) })}</span>
          <span className="mono">{t('science.tip.flux', { flux: formatNum(a.flux), err: formatNum(a.flux_err, 2), unit: a.unit })}</span>
          <span>{t('science.tip.epochs', { n: a.n_epochs })}</span>
          <span>{t('science.tip.flagged', { pct: (a.flagged_fraction * 100).toFixed(0) })}</span>
          <span>{t('science.tip.quality', { q: t(`science.quality.${a.quality}`) })}</span>
          <em className="muted">{t('science.tip.click')}</em>
        </div>
      )}
    </div>
  )
}
