// Qué cuadros forman el video. Lógica pura (sin React), testeada en sequence.test.ts.
//
// Problema de dominio: SPHEREx no saca "fotos" de una banda fija. Cada exposición de una visita
// cae en otro canal (~0.035 µm más, un ancho de banda), así que si se reproducen todos los cuadros
// de un detector en orden el brillo cambia por la λ y no por el objeto. Por eso:
//
//  - Banda fija (band != null): todos los cuadros de esa banda, por mjd. Son pocos (2–6 en
//    eps Ind B, WISE 0855 y RW Aur; ~34 en R Dra): el reproductor lo avisa.
//  - Todas las bandas (band == null): UN cuadro por fecha (día UTC) y por detector, el de λ más
//    cercana a una λ de referencia del detector (la mediana de las λ disponibles). Así el video
//    tiene tantas fechas como se pueda con λ parecida. La λ no queda idéntica entre fechas: el
//    reproductor muestra el rango (sequenceStats) para no esconderlo.
//
// Cuadros con ready === false (todavía bajando de IRSA): quedan FUERA de la secuencia. No traen λ,
// banda ni target_xy, así que no se pueden elegir ni dibujar; el reproductor muestra cuántos faltan
// y la secuencia crece sola a medida que llegan (frames.tsx re-pide cada 2.5 s).
//
// Calidad: con banda fija entran todos (son pocos y el badge avisa). Con todas las bandas, un cuadro
// 'bad' solo se elige si es lo único que hay ese día; 'suspect' pesa como un ancho de banda extra.
import type { Detector, Frame, Quality } from '../../api/types'

export interface SequenceOptions {
  band: number | null
}

export const isReady = (f: Frame) => f.ready !== false && f.wavelength_um != null

/** Día UTC del cuadro ('YYYY-MM-DD'). `date` viene en ISO UTC sin zona; si faltara, sale del mjd. */
export function dayKey(f: Frame): string {
  if (f.date && f.date.length >= 10) return f.date.slice(0, 10)
  return new Date((f.mjd - 40587) * 86400000).toISOString().slice(0, 10)
}

export function median(xs: number[]): number | null {
  if (!xs.length) return null
  const s = [...xs].sort((a, b) => a - b)
  const m = s.length >> 1
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

/** λ de referencia de un conjunto de cuadros (mediana de las λ de los cuadros listos). */
export function referenceWavelength(frames: Frame[]): number | null {
  return median(frames.filter(isReady).map(f => f.wavelength_um as number))
}

const QUALITY_PENALTY: Record<Quality, number> = { ok: 0, suspect: 1, bad: 1e6 }
const byMjd = (a: Frame, b: Frame) => a.mjd - b.mjd

/** Costo de elegir `f` para la λ `ref`: distancia en anchos de banda + penalidad por calidad. */
function cost(f: Frame, ref: number): number {
  const bw = f.bandwidth_um && f.bandwidth_um > 0 ? f.bandwidth_um : 0.035
  return Math.abs((f.wavelength_um as number) - ref) / bw + (f.quality ? QUALITY_PENALTY[f.quality] : 0)
}

export function buildSequence(frames: Frame[], o: SequenceOptions): Frame[] {
  const ready = frames.filter(isReady)
  if (o.band != null) return ready.filter(f => f.band === o.band).sort(byMjd)

  // referencia por detector (frames.tsx ya pide uno solo, pero no lo damos por sentado)
  const perDet = new Map<Detector, Frame[]>()
  for (const f of ready) {
    const l = perDet.get(f.detector)
    if (l) l.push(f); else perDet.set(f.detector, [f])
  }
  const out: Frame[] = []
  for (const fs of perDet.values()) {
    const ref = referenceWavelength(fs) as number
    const best = new Map<string, Frame>()
    for (const f of fs) {
      const k = dayKey(f)
      const cur = best.get(k)
      if (!cur) { best.set(k, f); continue }
      const d = cost(f, ref) - cost(cur, ref)
      if (d < 0 || (d === 0 && f.mjd < cur.mjd)) best.set(k, f)
    }
    out.push(...best.values())
  }
  return out.sort(byMjd)
}

export interface SequenceStats {
  n: number
  days: number
  wlMin: number | null
  wlMax: number | null
  /** cuántos cuadros 'bad' / 'suspect' quedaron adentro */
  bad: number
  suspect: number
}

export function sequenceStats(seq: Frame[]): SequenceStats {
  const wl = seq.filter(isReady).map(f => f.wavelength_um as number)
  return {
    n: seq.length,
    days: new Set(seq.map(dayKey)).size,
    wlMin: wl.length ? Math.min(...wl) : null,
    wlMax: wl.length ? Math.max(...wl) : null,
    bad: seq.filter(f => f.quality === 'bad').length,
    suspect: seq.filter(f => f.quality === 'suspect').length,
  }
}

export interface BandOption {
  band: number
  /** λ típica de la banda en estos cuadros (mediana) */
  wavelength_um: number
  /** ancho de banda típico (mediana) */
  bandwidth_um: number | null
  count: number
}

/** Bandas presentes en los cuadros (listos) de UN detector, ordenadas por número de banda. */
export function bandOptions(frames: Frame[]): BandOption[] {
  const by = new Map<number, Frame[]>()
  for (const f of frames.filter(isReady)) {
    if (f.band == null) continue
    const l = by.get(f.band)
    if (l) l.push(f); else by.set(f.band, [f])
  }
  return [...by.entries()]
    .map(([band, fs]) => ({
      band,
      wavelength_um: median(fs.map(f => f.wavelength_um as number)) as number,
      bandwidth_um: median(fs.filter(f => f.bandwidth_um != null).map(f => f.bandwidth_um as number)),
      count: fs.length,
    }))
    .sort((a, b) => a.band - b.band)
}

/** Rango de λ medido en los cuadros listos; null si no hay. */
export function wavelengthRange(frames: Frame[]): [number, number] | null {
  const wl = frames.filter(isReady).map(f => f.wavelength_um as number)
  return wl.length ? [Math.min(...wl), Math.max(...wl)] : null
}

/** Índice de la marca de "temporada": cuadros que arrancan después de un hueco de más de `gapDays`. */
export function seasonStarts(seq: Frame[], gapDays = 20): number[] {
  const out: number[] = []
  for (let i = 0; i < seq.length; i++) if (i === 0 || seq[i].mjd - seq[i - 1].mjd > gapDays) out.push(i)
  return out
}
