// Línea de tiempo: un input range (accesible y arrastrable) con una marca por cuadro y etiquetas de
// fecha al comienzo de cada temporada de observación (huecos de más de 20 días).
import type { Frame } from '../../api/types'
import type { LoadStatus } from './preload'
import { seasonStarts } from './sequence'

interface Props {
  sequence: Frame[]
  index: number
  status: (k: number) => LoadStatus | undefined
  onScrub: (k: number) => void
  onCommit: () => void
  label: string
  valueText: string
}

export default function Timeline({ sequence, index, status, onScrub, onCommit, label, valueText }: Props) {
  const n = sequence.length
  const pos = (k: number) => (n > 1 ? (k / (n - 1)) * 100 : 50)

  // etiquetas de temporada sin pisarse: como mínimo 18 % de separación
  const labels: number[] = []
  for (const k of seasonStarts(sequence)) if (!labels.length || pos(k) - pos(labels[labels.length - 1]) >= 18) labels.push(k)

  return (
    <div className="pl-timeline">
      <input
        type="range"
        min={0}
        max={Math.max(0, n - 1)}
        step={1}
        value={index}
        disabled={n < 2}
        aria-label={label}
        aria-valuetext={valueText}
        onChange={e => onScrub(Number(e.currentTarget.value))}
        onPointerUp={onCommit}
        onKeyUp={onCommit}
      />
      <div className="pl-ticks" aria-hidden="true">
        {sequence.map((f, k) => {
          const st = status(k)
          const cls = ['pl-tick',
            st === 'loaded' ? 'is-loaded' : st === 'error' ? 'is-error' : '',
            f.quality === 'bad' ? 'q-bad' : f.quality === 'suspect' ? 'q-suspect' : '',
            k === index ? 'is-current' : ''].filter(Boolean).join(' ')
          return <span key={f.id} className={cls} style={{ left: `${pos(k)}%` }} />
        })}
      </div>
      <div className="pl-tick-labels mono" aria-hidden="true">
        {labels.map(k => (
          // en los bordes se alinea hacia adentro para no desbordar en pantallas angostas
          <span key={k} style={{ left: `${pos(k)}%`, transform: `translateX(${pos(k) < 12 ? 0 : pos(k) > 88 ? -100 : -50}%)` }}>
            {sequence[k].date.slice(0, 7)}
          </span>
        ))}
      </div>
    </div>
  )
}
