// Posición actual de la vista, venga de donde venga.
// - Posición libre: la de la URL.
// - Objetivo: la que devuelve el backend (con movimiento propio aplicado) en /api/frames o
//   /api/coverage; mientras no llega, la de /api/targets o la copia local de targets.yaml.
import { useFrames } from '../../state/frames'
import { useView } from '../../state/view'
import type { QueryEcho, TargetKey } from '../../api/types'
import { findTarget, type NavTarget } from './targets'

export interface CurrentPosition {
  ra: number
  dec: number
  /** 'backend' = ya confirmada por /api/frames o /api/coverage */
  source: 'free' | 'backend' | 'targets'
  target: NavTarget | null
}

export function pickPosition(
  view: { target: TargetKey | null; ra: number | null; dec: number | null },
  echoes: (QueryEcho | null | undefined)[],
  targets: NavTarget[],
): CurrentPosition | null {
  if (!view.target) {
    return view.ra != null && view.dec != null ? { ra: view.ra, dec: view.dec, source: 'free', target: null } : null
  }
  const t = findTarget(targets, view.target)
  // una respuesta vieja de otro objetivo puede sobrevivir un render: se descarta
  const q = echoes.find(e => e && Number.isFinite(e.ra) && Number.isFinite(e.dec) && (e.target === undefined || e.target === view.target))
  if (q) return { ra: q.ra, dec: q.dec, source: 'backend', target: t }
  return t ? { ra: t.ra, dec: t.dec, source: 'targets', target: t } : null
}

export function useCurrentPosition(targets: NavTarget[]): CurrentPosition | null {
  const { view } = useView()
  const { response, coverage } = useFrames()
  return pickPosition(view, [response?.query, coverage?.query], targets)
}
