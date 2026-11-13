// Escenario: el PNG del cuadro agrandado sin suavizar, con la cruz del objetivo, el punto elegido y
// la capa de máscara encima. Las capas se dibujan en un SVG con viewBox = tamaño natural del PNG, así
// las coordenadas son píxeles del PNG (centro del píxel i en i + 0.5) y escalan solas.
import { useState, type MouseEvent } from 'react'
import type { Frame } from '../../api/types'
import { pixelToSky, skyToPixel } from '../../lib/sky'

interface Props {
  frame: Frame
  url: string
  /** '' = sin capa de máscara */
  maskUrl: string
  /** centro y lado del recorte (response.query): necesarios para pasar de píxel a cielo */
  center: { ra: number; dec: number; size: number } | null
  pick: { ra: number; dec: number } | null
  /** posiciones de referencia a marcar (p. ej. coordenadas del enunciado), en grados ICRS */
  refMarks?: { ra: number; dec: number; label: string }[]
  onPick: (p: { ra: number; dec: number }) => void
  waiting: boolean
  label: string
  title: string
  crossLabel: string
  pickLabel: string
  waitingLabel: string
}

export default function Stage(p: Props) {
  // todos los PNG de una consulta tienen el mismo tamaño (~59×59); hasta que carga el primero no hay capas
  const [nat, setNat] = useState<{ w: number; h: number } | null>(null)
  const W = nat?.w ?? 0, H = nat?.h ?? 0

  const onClick = (e: MouseEvent<HTMLDivElement>) => {
    if (!nat || !p.center) return
    const r = e.currentTarget.getBoundingClientRect()
    const x = ((e.clientX - r.left) / r.width) * W - 0.5
    const y = ((e.clientY - r.top) / r.height) * H - 0.5
    p.onPick(pixelToSky(x, y, W, H, p.center.ra, p.center.dec, p.center.size))
  }

  const xy = p.frame.target_xy
  const pk = nat && p.center && p.pick
    ? skyToPixel(p.pick.ra, p.pick.dec, W, H, p.center.ra, p.center.dec, p.center.size)
    : null
  const inside = (q: { x: number; y: number }) => q.x >= -0.5 && q.y >= -0.5 && q.x <= W - 0.5 && q.y <= H - 0.5
  const pickInside = pk && inside(pk)
  const refs = nat && p.center
    ? (p.refMarks ?? []).map(r => ({ ...r, ...skyToPixel(r.ra, r.dec, W, H, p.center!.ra, p.center!.dec, p.center!.size) })).filter(inside)
    : []

  // brazos de la cruz con un hueco en el centro para no tapar el objeto (en píxeles del PNG)
  const arm = (cx: number, cy: number) => {
    const g = 1.3, l = 4.5
    return [
      [cx - l, cy, cx - g, cy], [cx + g, cy, cx + l, cy],
      [cx, cy - l, cx, cy - g], [cx, cy + g, cx, cy + l],
    ]
  }

  return (
    <div
      className="pl-stage"
      style={nat ? { aspectRatio: `${W} / ${H}` } : undefined}
      role="img"
      aria-label={p.label}
      title={p.center ? p.title : undefined}
      onClick={onClick}
    >
      <img
        className="pl-img"
        src={p.url}
        alt=""
        draggable={false}
        onLoad={e => {
          const im = e.currentTarget
          if (im.naturalWidth && (im.naturalWidth !== W || im.naturalHeight !== H)) setNat({ w: im.naturalWidth, h: im.naturalHeight })
        }}
      />
      {p.maskUrl && <img className="pl-mask" src={p.maskUrl} alt="" draggable={false} />}
      {nat && (
        <svg className="pl-overlay" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
          {xy && (
            <g className="pl-cross">
              <title>{p.crossLabel}</title>
              {arm(xy[0] + 0.5, xy[1] + 0.5).map(([x1, y1, x2, y2], k) => (
                <line key={k} x1={x1} y1={y1} x2={x2} y2={y2} vectorEffect="non-scaling-stroke" />
              ))}
            </g>
          )}
          {refs.map((r, k) => (
            <g key={k} className="pl-ref">
              <title>{r.label}</title>
              {/* rombo: posición de catálogo, distinta de la cruz (dónde está el objeto ese día) */}
              <polygon points={`${r.x + 0.5},${r.y - 2} ${r.x + 3},${r.y + 0.5} ${r.x + 0.5},${r.y + 3} ${r.x - 2},${r.y + 0.5}`}
                vectorEffect="non-scaling-stroke" />
            </g>
          ))}
          {pk && pickInside && (
            <g className="pl-pick">
              <title>{p.pickLabel}</title>
              {/* radio = apertura del espectro (aperture_px 2.5 en el contrato) */}
              <circle cx={pk.x + 0.5} cy={pk.y + 0.5} r={2.5} vectorEffect="non-scaling-stroke" />
            </g>
          )}
        </svg>
      )}
      {p.waiting && <div className="pl-waiting" role="status">{p.waitingLabel}</div>}
      {/* filtro para teñir la capa de máscara con --mask conservando su alfa */}
      <svg className="pl-defs" aria-hidden="true" focusable="false">
        <filter id="pl-mask-tint" colorInterpolationFilters="sRGB">
          <feFlood className="pl-mask-flood" result="c" />
          <feComposite in="c" in2="SourceGraphic" operator="in" />
        </filter>
      </svg>
    </div>
  )
}
