// Lógica pura del panel de inspección: comparabilidad aproximada para la resta, elección del cuadro
// de referencia, lectura defensiva de los extras de /meta, motivos de `quality` y formatos.
// Sin React: todo se prueba en logic.test.ts.
import type { ApiError } from '../../api/client'
import type { Frame, FrameMeta } from '../../api/types'
import { isPhotometryMasked } from './bits'

// ---------------------------------------------------------------------------------------------
// Comparabilidad (ayuda del lado del cliente; la verdad la da el backend con core.is_comparable)

/** Igual que core/subtract.py MAX_DLAMBDA_FRACTION: |Δλ| ≤ 0.5 · min(ancho de banda). */
export const MAX_DLAMBDA_FRACTION = 0.5

export type CompareLevel = 'likely' | 'unknown' | 'unlikely'
export type CompareReason = 'same' | 'detector' | 'wavelength_ok' | 'wavelength' | 'band_ok' | 'band' | 'missing'

export interface CompareHint {
  level: CompareLevel
  reason: CompareReason
  /** |Δλ| y tolerancia en µm, cuando se pudo calcular */
  dlam?: number
  tol?: number
}

type FrameLike = Pick<Frame, 'id' | 'detector' | 'wavelength_um' | 'bandwidth_um' | 'band'>

/**
 * Misma regla que core.is_comparable, hasta donde se puede sin los arrays: mismo detector y
 * λ dentro de media banda. Si todavía no hay λ (ready=false), cae a "misma banda"; si tampoco hay
 * banda, no se sabe.
 */
export function compareHint(a: FrameLike, b: FrameLike): CompareHint {
  if (a.id === b.id) return { level: 'unlikely', reason: 'same' }
  if (a.detector !== b.detector) return { level: 'unlikely', reason: 'detector' }
  if (a.wavelength_um != null && b.wavelength_um != null && a.bandwidth_um != null && b.bandwidth_um != null) {
    const dlam = Math.abs(a.wavelength_um - b.wavelength_um)
    const tol = MAX_DLAMBDA_FRACTION * Math.min(a.bandwidth_um, b.bandwidth_um)
    return dlam <= tol ? { level: 'likely', reason: 'wavelength_ok', dlam, tol } : { level: 'unlikely', reason: 'wavelength', dlam, tol }
  }
  if (a.band != null && b.band != null) {
    return a.band === b.band ? { level: 'likely', reason: 'band_ok' } : { level: 'unlikely', reason: 'band' }
  }
  return { level: 'unknown', reason: 'missing' }
}

export interface Candidate {
  frame: Frame
  hint: CompareHint
  /** |Δt| en días respecto de A */
  dt: number
}

/** Candidatos a B agrupados por nivel; dentro de cada grupo, de más a menos separados en el tiempo. */
export function candidates(a: Frame, frames: Frame[]): Record<CompareLevel, Candidate[]> {
  const out: Record<CompareLevel, Candidate[]> = { likely: [], unknown: [], unlikely: [] }
  for (const f of frames) {
    if (f.id === a.id) continue
    const hint = compareHint(a, f)
    out[hint.level].push({ frame: f, hint, dt: Math.abs(f.mjd - a.mjd) })
  }
  for (const k of Object.keys(out) as CompareLevel[]) out[k].sort((x, y) => y.dt - x.dt || x.frame.id.localeCompare(y.frame.id))
  return out
}

/**
 * B por defecto: el comparable más lejano en el tiempo (maximiza el movimiento del objeto). Si no hay
 * ninguno probable, el más lejano de los que no se sabe. Nunca uno que probablemente no sea comparable.
 */
export function defaultReference(a: Frame | null, frames: Frame[]): Frame | null {
  if (!a) return null
  const c = candidates(a, frames)
  return c.likely[0]?.frame ?? c.unknown[0]?.frame ?? null
}

// ---------------------------------------------------------------------------------------------
// Estado de la resta según lo que contestó el backend

export type DiffStatus =
  | { kind: 'ok' }
  | { kind: 'not_comparable'; detail: string }
  | { kind: 'pending_backend' }
  | { kind: 'network'; detail: string }
  | { kind: 'error'; status: number; detail: string }

/**
 * 422 = no comparables (motivo de core.is_comparable). 404 de ruta inexistente (FastAPI responde
 * detail "Not Found") o 501 = /api/diff todavía no está en el backend. 0 = sin conexión.
 */
export function classifyDiff(e: Pick<ApiError, 'status' | 'code' | 'message'> | null): DiffStatus {
  if (!e) return { kind: 'ok' }
  if (e.status === 422) return { kind: 'not_comparable', detail: e.message }
  if (e.status === 501) return { kind: 'pending_backend' }
  if (e.status === 404 && (e.code === 'not_found' || e.code === 'http_404') && (!e.message || /^not found$/i.test(e.message)))
    return { kind: 'pending_backend' }
  if (e.status === 0) return { kind: 'network', detail: e.message }
  return { kind: 'error', status: e.status, detail: e.message }
}

// ---------------------------------------------------------------------------------------------
// Extras de /meta que el backend agrega sin estar en types.ts (decisión 10 del contrato)

export interface MetaExtras {
  flagged_fraction?: number
  target?: { key?: string; xy?: [number, number]; inside?: boolean; radec?: [number, number] }
  dqa?: { l1?: string; l2?: string }
  bunit?: string
  shape?: [number, number]
}

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const isPair = (v: unknown): v is [number, number] => Array.isArray(v) && v.length === 2 && isNum(v[0]) && isNum(v[1])
const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v != null && !Array.isArray(v)

/** Lee los extras sin confiar en la forma: lo que no tenga el tipo esperado se ignora. */
export function readExtras(m: FrameMeta): MetaExtras {
  const r = m as unknown as Record<string, unknown>
  const x: MetaExtras = {}
  if (isNum(r.flagged_fraction)) x.flagged_fraction = r.flagged_fraction
  if (isObj(r.target)) {
    const t = r.target
    x.target = {}
    if (typeof t.key === 'string') x.target.key = t.key
    if (isPair(t.xy)) x.target.xy = t.xy
    if (typeof t.inside === 'boolean') x.target.inside = t.inside
    if (isPair(t.radec)) x.target.radec = t.radec
  }
  if (isObj(r.dqa)) {
    x.dqa = {}
    if (typeof r.dqa.l1 === 'string') x.dqa.l1 = r.dqa.l1
    if (typeof r.dqa.l2 === 'string') x.dqa.l2 = r.dqa.l2
  }
  if (typeof r.bunit === 'string') x.bunit = r.bunit
  if (isPair(r.shape)) x.shape = r.shape
  return x
}

/** Píxeles del recorte: de `shape` si viene; si no, se deduce de una fila (pixels / fraction). */
export function cutoutPixels(m: FrameMeta, x: MetaExtras = readExtras(m)): number | null {
  if (x.shape) return x.shape[0] * x.shape[1]
  const row = m.flags.cutout_counts.find(c => c.fraction > 0)
  return row ? Math.round(row.pixels / row.fraction) : null
}

// ---------------------------------------------------------------------------------------------
// Por qué un cuadro es ok / suspect / bad (decisión 7 del contrato)

export type QualityReason =
  | { key: 'outside' }
  | { key: 'l2_qa'; value: string }
  | { key: 'target_masked'; bits: string[] }
  | { key: 'over_half'; fraction: number }

export function qualityReasons(m: FrameMeta, x: MetaExtras = readExtras(m)): QualityReason[] {
  const out: QualityReason[] = []
  if (x.target?.inside === false) out.push({ key: 'outside' })
  if (x.dqa?.l2 && !/^pass$/i.test(x.dqa.l2)) out.push({ key: 'l2_qa', value: x.dqa.l2 })
  const masked = (m.flags.at_target ?? []).filter(isPhotometryMasked)
  if (masked.length) out.push({ key: 'target_masked', bits: masked })
  if (x.flagged_fraction != null && x.flagged_fraction > 0.5) out.push({ key: 'over_half', fraction: x.flagged_fraction })
  return out
}

// ---------------------------------------------------------------------------------------------
// Formatos

export type Lang = 'en' | 'es'
const locale = (lang: Lang) => (lang === 'es' ? 'es-AR' : 'en-US')

export function fmtNum(n: number, digits: number, lang: Lang): string {
  return n.toLocaleString(locale(lang), { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: false })
}

export function fmtInt(n: number, lang: Lang): string {
  return Math.round(n).toLocaleString(locale(lang))
}

/** Fracción → porcentaje legible: 0 %, <0.1 %, 2.0 %, 45 %. */
export function fmtPct(fraction: number, lang: Lang): string {
  if (!(fraction > 0)) return '0 %'
  const p = fraction * 100
  if (p < 0.1) return `<${fmtNum(0.1, 1, lang)} %`
  return `${fmtNum(p, p < 10 ? 1 : 0, lang)} %`
}

/** '2025-05-05T16:49:00.018' → '2025-05-05 16:49:00 UTC' (el backend manda UTC sin zona). */
export function fmtDateUtc(iso: string): string {
  const m = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})/.exec(iso)
  return m ? `${m[1]} ${m[2]} UTC` : iso
}

/** 'spherex_qr3_deep' → 'QR3 deep'. Lo que no reconoce lo devuelve igual. */
export function fmtCollection(c: string | undefined | null): string {
  if (!c) return '—'
  const m = /^(?:spherex_)?(qr\d+)(_deep)?$/i.exec(c)
  return m ? `${m[1].toUpperCase()}${m[2] ? ' deep' : ''}` : c
}

/** Poder de resolución R = λ / Δλ, redondeado. */
export function resolvingPower(lambda: number, width: number): number | null {
  return width > 0 ? Math.round(lambda / width) : null
}
