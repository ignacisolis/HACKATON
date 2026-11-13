// Piezas chicas compartidas por las tres pestañas.
import { useState } from 'react'
import { useT } from '../../i18n'

/** Alarma C1: el release trae bits que ni el Supplement ni el header FITS documentan. */
export function UndocumentedAlarm({ bits }: { bits: number[] }) {
  const t = useT()
  if (!bits.length) return null
  return (
    <p className="notice error ins-alarm" role="alert">
      {t('inspect.undocumented', { bits: bits.join(', ') })}
    </p>
  )
}

export interface Marker { xy: [number, number] | null; kind: 'a' | 'b' }

/**
 * PNG del backend agrandado con píxeles nítidos, con marcas opcionales en coordenadas del PNG
 * (base 0, x a la derecha, y hacia abajo). Montar con key={src} para que se reinicie el estado.
 */
export function SkyImage({ src, alt, markers = [], caption }: { src: string; alt: string; markers?: Marker[]; caption?: string }) {
  const t = useT()
  const [dims, setDims] = useState<{ w: number; h: number } | null>(null)
  const [failed, setFailed] = useState(!src)
  return (
    <figure className="ins-fig">
      <div className="ins-img">
        {failed
          ? <div className="ins-img-error muted">{t('inspect.diff.imgError')}</div>
          : <img src={src} alt={alt} decoding="async"
              onLoad={e => setDims({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
              onError={() => setFailed(true)} />}
        {dims && !failed && markers.map((m, i) => m.xy && (
          <span key={i} aria-hidden="true" className={`ins-mark ${m.kind}`}
            style={{ left: `${((m.xy[0] + 0.5) / dims.w) * 100}%`, top: `${((m.xy[1] + 0.5) / dims.h) * 100}%` }} />
        ))}
      </div>
      {caption && <figcaption>{caption}</figcaption>}
    </figure>
  )
}
