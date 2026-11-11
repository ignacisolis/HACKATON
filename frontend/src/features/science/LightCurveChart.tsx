// Curva de luz de una banda: flujo vs. fecha, con barras de error. Para R Dra (Mira, ~245 d) en
// ~522 días de cobertura se tienen que ver dos ciclos. Línea vertical opcional = cuadro del video.
import { useId, useRef } from 'react'
import type { Lang } from '../../state/view'
import { useT } from '../../i18n'
import { mjdToDate } from '../../lib/sky'
import { clamp, extentWithErrors, formatNum, linearScale, monthTicks, niceLinearTicks } from './chart'
import { useChartCursor, useWidth } from './hooks'
import type { LcRow } from './spectrum'

interface Props {
  rows: LcRow[]
  unit: string
  color: string
  band: number
  lang: Lang
  /** MJD del cuadro que muestra el video, si hay */
  currentMjd: number | null
}

const fmtDate = (mjd: number, lang: Lang, o: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat(lang, { timeZone: 'UTC', ...o }).format(mjdToDate(mjd))

export default function LightCurveChart({ rows, unit, color, band, lang, currentMjd }: Props) {
  const t = useT()
  const uid = useId()
  const wrap = useRef<HTMLDivElement>(null)
  const width = Math.max(240, useWidth(wrap))
  const narrow = width < 480
  const H = narrow ? 210 : 240
  const M = { l: narrow ? 42 : 52, r: 12, t: 14, b: 38 }
  const plotB = H - M.b

  const m0 = rows[0].mjd, m1 = rows[rows.length - 1].mjd
  const padX = Math.max(5, (m1 - m0) * 0.03)
  const x = linearScale([m0 - padX, m1 + padX], [M.l, width - M.r])
  const dom = extentWithErrors(rows.map(r => ({ v: r.flux, err: r.err })), 'linear') ?? [0, 1]
  const y = linearScale(dom, [plotB, M.t])
  const xTicks = monthTicks(m0 - padX, m1 + padX, narrow ? 4 : 7)
  const yTicks = niceLinearTicks(dom[0], dom[1], narrow ? 4 : 5)
  const pos = rows.map(r => ({ x: x(r.mjd), y: y(r.flux) }))
  const { active, handlers } = useChartCursor(pos, { maxDist: narrow ? 30 : 24 })
  const yc = (v: number) => clamp(v, M.t, plotB)
  const nowX = currentMjd != null && currentMjd >= m0 - padX && currentMjd <= m1 + padX ? x(currentMjd) : null

  const a = active != null ? rows[active] : null
  const from = fmtDate(m0, lang, { dateStyle: 'medium' }), to = fmtDate(m1, lang, { dateStyle: 'medium' })
  const titleId = `${uid}-t`, descId = `${uid}-d`

  return (
    <div className="sci-chart" ref={wrap}>
      <svg width={width} height={H} viewBox={`0 0 ${width} ${H}`} className="sci-svg" role="img"
        aria-labelledby={`${titleId} ${descId}`} tabIndex={0} {...handlers}>
        <title id={titleId}>{t('science.lc.title')}</title>
        <desc id={descId}>{t('science.lc.desc', { band, n: rows.length, from, to })}</desc>

        {yTicks.map(v => (
          <g key={`y${v}`}>
            <line x1={M.l} x2={width - M.r} y1={y(v)} y2={y(v)} className="sci-grid" />
            <text x={M.l - 5} y={y(v)} dy="0.32em" textAnchor="end" className="sci-tick">{formatNum(v)}</text>
          </g>
        ))}
        {xTicks.map(v => (
          <g key={`x${v}`}>
            <line x1={x(v)} x2={x(v)} y1={M.t} y2={plotB} className="sci-grid" />
            <text x={x(v)} y={plotB + 15} textAnchor="middle" className="sci-tick">
              {fmtDate(v, lang, { month: 'short', year: '2-digit' })}
            </text>
          </g>
        ))}
        <line x1={M.l} x2={width - M.r} y1={plotB} y2={plotB} className="sci-axis" />
        <line x1={M.l} x2={M.l} y1={M.t} y2={plotB} className="sci-axis" />
        <text x={(M.l + width - M.r) / 2} y={H - 4} textAnchor="middle" className="sci-axislabel">{t('science.axis.date')}</text>
        <text transform={`translate(11 ${(M.t + plotB) / 2}) rotate(-90)`} textAnchor="middle" className="sci-axislabel">
          {t('science.axis.flux', { unit })}
        </text>

        {nowX != null && (
          <g className="sci-now">
            <line x1={nowX} x2={nowX} y1={M.t} y2={plotB} />
            <text x={nowX + (nowX > width / 2 ? -4 : 4)} y={M.t + 10}
              textAnchor={nowX > width / 2 ? 'end' : 'start'}>{t('science.lc.current')}</text>
          </g>
        )}

        <g style={{ color }}>
          <polyline points={pos.map(p => `${p.x},${p.y}`).join(' ')} className="sci-lcline" />
          {rows.map((r, i) => (
            <g key={`${r.mjd}-${i}`} className="sci-pt">
              <line x1={pos[i].x} x2={pos[i].x} y1={yc(y(r.flux - r.err))} y2={yc(y(r.flux + r.err))} className="sci-err" />
              <circle cx={pos[i].x} cy={pos[i].y} r={narrow ? 2.6 : 3} className="sci-dot" />
              {i === active && <circle cx={pos[i].x} cy={pos[i].y} r={6} className="sci-activering" />}
            </g>
          ))}
        </g>
      </svg>

      {a && active != null && (
        <div className="sci-tip" role="status"
          style={pos[active].x > width / 2 ? { left: M.l + 6, top: M.t + 4 } : { right: M.r + 6, top: M.t + 4 }}>
          <strong>{fmtDate(a.mjd, lang, { dateStyle: 'medium', timeStyle: 'short' })} UTC</strong>
          <span className="mono">MJD {a.mjd.toFixed(3)}</span>
          <span className="mono">{t('science.tip.flux', { flux: formatNum(a.flux), err: formatNum(a.err, 2), unit })}</span>
        </div>
      )}
    </div>
  )
}
