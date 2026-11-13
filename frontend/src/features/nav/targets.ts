// Objetivos de la demo (O5) y helpers puros de posición para el panel de navegación y Aladin.
// La lista viene de GET /api/targets; si falla, se usa NAV_TARGETS_FALLBACK, copiado de
// config/targets.yaml (generado 2026-11-10T22:05:45Z con core/fetch_targets.py).
import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { BestPair, MotionClaim, TargetKey } from '../../api/types'

export const SPHEREX_PIXEL_ARCSEC = 6.2
/** Lados de recorte ofrecidos (grados). 0.3 es el máximo que acepta el backend. */
export const FOV_OPTIONS = [0.05, 0.1, 0.2, 0.3] as const

export interface NavTarget {
  key: TargetKey
  name: string
  /** posición en la ventana de SPHEREx (con movimiento propio aplicado), grados ICRS */
  ra: number
  dec: number
  /** posición de catálogo a época J2000.0 (SIMBAD) */
  j2000: { ra: number; dec: number }
  simbadId: string
  /** movimiento propio total, ″/año */
  pmArcsecYr: number
  /** true si la deriva J2000→SPHEREx supera medio píxel (pm_correction: required) */
  pmRequired: boolean
  /** coordenadas del enunciado, si las hay (WISE 0855: época de descubrimiento ~2010.5) */
  statement?: { ra: number; dec: number }
  /** de /api/targets: la resta que mejor muestra el movimiento y qué tan firme es (solo con backend) */
  bestPair?: BestPair | null
  motion?: MotionClaim | null
}

const mid = (a: number, b: number) => (a + b) / 2

// ra/dec = punto medio entre spherex_start (2025-04-24) y spherex_end (2026-10-02) del YAML.
// El backend propaga a una fecha concreta (coord_epoch_applied); la diferencia es < 0.5 px.
export const NAV_TARGETS_FALLBACK: NavTarget[] = [
  {
    key: 'eps_ind_b', name: 'Epsilon Indi B (Ba+Bb)', simbadId: '* eps Ind B',
    ra: mid(331.09527441, 331.09818493), dec: mid(-56.80017699, -56.80116257),
    j2000: { ra: 331.04414659, dec: -56.7828442 }, pmArcsecYr: 4.6842, pmRequired: true,
  },
  {
    key: 'wise_0855', name: 'WISE 0855-0714', simbadId: 'WISEA J085510.74-071442.5',
    ra: mid(133.76133467, 133.75805885), dec: mid(-7.2423114, -7.24204168),
    j2000: { ra: 133.81890825, dec: -7.247048 }, pmArcsecYr: 8.1515, pmRequired: true,
    statement: { ra: 133.79512917, dec: -7.24514722 },
  },
  {
    key: 'rw_aur', name: 'RW Aurigae A', simbadId: 'V* RW Aur A',
    ra: mid(76.95608912, 76.95609034), dec: mid(30.40113373, 30.40112277),
    j2000: { ra: 76.95606759, dec: 30.40132636 }, pmArcsecYr: 0.0275, pmRequired: false,
  },
  {
    key: 'r_dra', name: 'R Draconis', simbadId: 'V* R Dra',
    ra: mid(248.16724309, 248.16722217), dec: mid(66.75502265, 66.75502511),
    j2000: { ra: 248.16761083, dec: 66.75497942 }, pmArcsecYr: 0.0215, pmRequired: false,
  },
]

export const findTarget = (list: NavTarget[], key: TargetKey | null) =>
  key ? list.find(t => t.key === key) ?? NAV_TARGETS_FALLBACK.find(t => t.key === key) ?? null : null

// --- carga compartida (NavPanel y SkyContext piden lo mismo: un solo fetch) ---

let cache: Promise<{ list: NavTarget[]; fromApi: boolean }> | null = null

export function loadTargets() {
  cache ??= api.targets()
    .then(remote => {
      const list = NAV_TARGETS_FALLBACK.map(fb => {
        const r = remote.find(x => x.key === fb.key)
        return r && Number.isFinite(r.ra) && Number.isFinite(r.dec)
          ? { ...fb, name: r.name || fb.name, ra: r.ra, dec: r.dec, bestPair: r.best_pair ?? null, motion: r.motion ?? null }
          : fb
      })
      return { list, fromApi: true }
    })
    .catch(() => {
      cache = null // reintentar en el próximo montaje
      return { list: NAV_TARGETS_FALLBACK, fromApi: false }
    })
  return cache
}

export function useTargets(): { list: NavTarget[]; fromApi: boolean | null } {
  const [s, setS] = useState<{ list: NavTarget[]; fromApi: boolean | null }>({ list: NAV_TARGETS_FALLBACK, fromApi: null })
  useEffect(() => {
    let alive = true
    loadTargets().then(r => { if (alive) setS(r) })
    return () => { alive = false }
  }, [])
  return s
}

// --- geometría ---

const RAD = Math.PI / 180

/** Separación angular en grados (haversine). */
export function angularSepDeg(ra1: number, dec1: number, ra2: number, dec2: number): number {
  const s = Math.sin(((dec2 - dec1) * RAD) / 2) ** 2
    + Math.cos(dec1 * RAD) * Math.cos(dec2 * RAD) * Math.sin(((ra2 - ra1) * RAD) / 2) ** 2
  return (2 * Math.asin(Math.min(1, Math.sqrt(s)))) / RAD
}

/** Esquinas del recorte de SPHEREx (norte arriba), misma aproximación tangente que lib/sky.ts. */
export function fovCorners(ra0: number, dec0: number, sizeDeg: number): [number, number][] {
  const h = sizeDeg / 2
  const c = Math.max(Math.cos(dec0 * RAD), 1e-6)
  const norm = (r: number) => ((r % 360) + 360) % 360
  return [
    [norm(ra0 + h / c), dec0 + h], // NE (arriba a la izquierda)
    [norm(ra0 - h / c), dec0 + h], // NO
    [norm(ra0 - h / c), dec0 - h], // SO
    [norm(ra0 + h / c), dec0 - h], // SE
  ]
}

/** Lado del recorte en píxeles de SPHEREx (~6.2″/px). */
export const fovToPixels = (fovDeg: number) => Math.round((fovDeg * 3600) / SPHEREX_PIXEL_ARCSEC)

/** Campo de Aladin: el recorte con margen, para que se vea el rectángulo y el entorno. */
export const contextFov = (fovDeg: number) => Math.min(Math.max(fovDeg * 3, 0.2), 1)

/**
 * Si una posición libre cae cerca de un objetivo de movimiento propio alto (de su posición de
 * catálogo, de la del enunciado o de la actual), lo devuelve: conviene usar el atajo.
 */
export function nearbyHighPmTarget(ra: number, dec: number, list: NavTarget[], radiusDeg = 0.05): NavTarget | null {
  for (const t of list) {
    if (!t.pmRequired) continue
    const pts = [t.j2000, { ra: t.ra, dec: t.dec }, ...(t.statement ? [t.statement] : [])]
    if (pts.some(p => angularSepDeg(ra, dec, p.ra, p.dec) <= radiusDeg)) return t
  }
  return null
}

// --- enlaces externos (C9) ---

const signed = (dec: number) => (dec >= 0 ? '+' : '') + dec.toFixed(5)

export function aladinUrl(ra: number, dec: number, fovDeg: number): string {
  return `https://aladin.cds.unistra.fr/AladinLite/?target=${encodeURIComponent(`${ra.toFixed(5)} ${signed(dec)}`)}&fov=${fovDeg}`
}

/** Búsqueda por coordenadas en SIMBAD (radio 30″). */
export function simbadCoordUrl(ra: number, dec: number, radiusArcsec = 30): string {
  return `https://simbad.cds.unistra.fr/simbad/sim-coo?Coord=${encodeURIComponent(`${ra.toFixed(5)} ${signed(dec)}`)}&Radius=${radiusArcsec}&Radius.unit=arcsec`
}

/** Búsqueda por identificador: para objetivos de movimiento propio alto, SIMBAD compara contra
 *  J2000 y una búsqueda de 30″ en la posición de 2025-26 no los encuentra. */
export function simbadIdUrl(simbadId: string): string {
  return `https://simbad.cds.unistra.fr/simbad/sim-id?Ident=${encodeURIComponent(simbadId)}`
}
