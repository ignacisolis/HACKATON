// Enlaces a Aladin y SIMBAD con la posición actual (tarea 29, C9).
import { useT } from '../../i18n'
import type { CurrentPosition } from './position'
import { aladinUrl, simbadCoordUrl, simbadIdUrl } from './targets'
import './nav.css'

export default function ExternalLinks({ pos, fov }: { pos: CurrentPosition | null; fov: number }) {
  const t = useT()
  if (!pos) return null
  // objetivo de movimiento propio alto: SIMBAD por nombre (su posición es J2000, no la de 2025-26)
  const byId = pos.target?.pmRequired ? pos.target.simbadId : null
  return (
    <div className="nav-links">
      <a className="btn" href={aladinUrl(pos.ra, pos.dec, fov)} target="_blank" rel="noopener">
        {t('nav.openAladin')} <span aria-hidden="true">↗</span><span className="nav-sr">{t('nav.newTab')}</span>
      </a>
      <a className="btn" href={byId ? simbadIdUrl(byId) : simbadCoordUrl(pos.ra, pos.dec)} target="_blank" rel="noopener"
        title={byId ? t('nav.simbadById') : undefined}>
        {t('nav.openSimbad')} <span aria-hidden="true">↗</span><span className="nav-sr">{t('nav.newTab')}</span>
      </a>
    </div>
  )
}
