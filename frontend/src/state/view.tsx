// Estado de la vista = la URL (C4). Todo lo que define "qué está mirando el usuario" vive acá y se
// refleja en ?target=&ra=&dec=&fov=&det=&band=&t=&…, así un link reproduce exactamente la vista.
// Lo efímero (hover, play/pausa, carga) NO va acá: queda en el estado local de cada componente.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Detector, SkyQuery, Stretch, TargetKey } from '../api/types'
import { DETECTORS } from '../api/types'

const TARGET_KEYS: TargetKey[] = ['eps_ind_b', 'wise_0855', 'rw_aur', 'r_dra']
export type Lang = 'en' | 'es'

export interface ViewState {
  /** objetivo de la demo; si está, gana sobre ra/dec (el backend aplica movimiento propio) */
  target: TargetKey | null
  ra: number | null
  dec: number | null
  /** lado del recorte en grados (param `size` de la API) */
  fov: number
  /** detector del video; null = todavía no elegido (el reproductor elige el de más fechas) */
  det: Detector | null
  /** banda fija 1..102; null = todas las bandas del detector */
  band: number | null
  /** índice del cuadro en la secuencia que muestra el reproductor */
  t: number
  stretch: Stretch
  /** restar luz zodiacal (layer=image-zodi) */
  zodi: boolean
  /** bits de FLAGS prendidos como capa sobre la imagen (C6) */
  mask: string[]
  /** cuadro contra el que se resta el actual (C5); id de cuadro o null */
  diff: string | null
  /** punto elegido con click para el espectro (grados ICRS); null = centro */
  pick: { ra: number; dec: number } | null
  lang: Lang
}

export const DEFAULT_VIEW: ViewState = {
  target: 'r_dra', ra: null, dec: null, fov: 0.1, det: null, band: null, t: 0,
  stretch: 'asinh', zodi: false, mask: [], diff: null, pick: null,
  lang: (typeof navigator !== 'undefined' && navigator.language?.startsWith('es')) ? 'es' : 'en',
}

const num = (s: string | null) => (s == null || s === '' || isNaN(Number(s)) ? null : Number(s))

export function parseView(search: string): ViewState {
  const p = new URLSearchParams(search)
  const v: ViewState = { ...DEFAULT_VIEW }
  const target = p.get('target') as TargetKey | null
  const ra = num(p.get('ra')), dec = num(p.get('dec'))
  if (target && TARGET_KEYS.includes(target)) v.target = target
  else if (ra != null && dec != null) { v.target = null; v.ra = ra; v.dec = dec }
  const fov = num(p.get('fov')); if (fov && fov > 0 && fov <= 0.3) v.fov = fov
  const det = p.get('det')?.toUpperCase() as Detector | undefined; if (det && DETECTORS.includes(det)) v.det = det
  const band = num(p.get('band')); if (band && band >= 1 && band <= 102) v.band = Math.round(band)
  const t = num(p.get('t')); if (t != null && t >= 0) v.t = Math.floor(t)
  if (p.get('stretch') === 'linear') v.stretch = 'linear'
  if (p.get('zodi') === '1') v.zodi = true
  const mask = p.get('mask'); if (mask) v.mask = mask.split(',').filter(Boolean)
  const diff = p.get('diff'); if (diff && /^[0-9A-Za-z_]+$/.test(diff)) v.diff = diff
  const pra = num(p.get('pra')), pdec = num(p.get('pdec')); if (pra != null && pdec != null) v.pick = { ra: pra, dec: pdec }
  const lang = p.get('lang'); if (lang === 'en' || lang === 'es') v.lang = lang
  return v
}

export function serializeView(v: ViewState): string {
  const p = new URLSearchParams()
  if (v.target) p.set('target', v.target)
  else if (v.ra != null && v.dec != null) { p.set('ra', v.ra.toFixed(5)); p.set('dec', v.dec.toFixed(5)) }
  if (v.fov !== DEFAULT_VIEW.fov) p.set('fov', String(v.fov))
  if (v.det) p.set('det', v.det)
  if (v.band != null) p.set('band', String(v.band))
  if (v.t) p.set('t', String(v.t))
  if (v.stretch !== 'asinh') p.set('stretch', v.stretch)
  if (v.zodi) p.set('zodi', '1')
  if (v.mask.length) p.set('mask', v.mask.join(','))
  if (v.diff) p.set('diff', v.diff)
  if (v.pick) { p.set('pra', v.pick.ra.toFixed(5)); p.set('pdec', v.pick.dec.toFixed(5)) }
  p.set('lang', v.lang)
  return p.toString()
}

/** Lo que se le pide al backend para esta vista. */
export function skyQueryOf(v: ViewState): SkyQuery | null {
  if (v.target) return { target: v.target, size: v.fov }
  if (v.ra != null && v.dec != null) return { ra: v.ra, dec: v.dec, size: v.fov }
  return null
}

/** Clave estable de la posición: cuando cambia, el resto de la vista (t, diff, pick) se resetea. */
export const positionKey = (v: ViewState) => `${v.target ?? `${v.ra},${v.dec}`}|${v.fov}`

type Patch = Partial<ViewState> | ((v: ViewState) => Partial<ViewState>)
interface Ctx { view: ViewState; setView: (p: Patch) => void; shareUrl: string }
const ViewCtx = createContext<Ctx | null>(null)

export function ViewProvider({ children }: { children: ReactNode }) {
  const [view, setState] = useState<ViewState>(() => parseView(window.location.search))

  const setView = useCallback((patch: Patch) => {
    setState(prev => {
      const delta = typeof patch === 'function' ? patch(prev) : patch
      const next = { ...prev, ...delta }
      // cambiar de posición invalida todo lo que dependía de los cuadros anteriores
      if (positionKey(next) !== positionKey(prev)) {
        if (!('t' in delta)) next.t = 0
        if (!('diff' in delta)) next.diff = null
        if (!('pick' in delta)) next.pick = null
        if (!('det' in delta)) next.det = null
        if (!('band' in delta)) next.band = null
      }
      return next
    })
  }, [])

  const qs = serializeView(view)
  useEffect(() => {
    const u = `${window.location.pathname}?${qs}`
    if (u !== `${window.location.pathname}${window.location.search}`) window.history.replaceState(null, '', u)
  }, [qs])

  useEffect(() => {
    const onPop = () => setState(parseView(window.location.search))
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  useEffect(() => { document.documentElement.lang = view.lang }, [view.lang])

  const value = useMemo(() => ({ view, setView, shareUrl: `${window.location.origin}${window.location.pathname}?${qs}` }), [view, setView, qs])
  return <ViewCtx.Provider value={value}>{children}</ViewCtx.Provider>
}

export function useView(): Ctx {
  const c = useContext(ViewCtx)
  if (!c) throw new Error('useView fuera de <ViewProvider>')
  return c
}
