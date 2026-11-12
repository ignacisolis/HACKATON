// Contexto de cielo con Aladin Lite v3 (C9, decisión de Bruno): el mismo lugar en otros
// relevamientos, sincronizado con la vista. Centro = posición actual; rectángulo = recorte de
// SPHEREx; marcadores = posición en SPHEREx y, si el objetivo se mueve rápido, la de catálogo J2000.
//
// Integración: paquete npm `aladin-lite` (3.9.2-beta) con import() dinámico. El WebAssembly viene
// embebido en base64 dentro de dist/aladin.js, así que Vite lo empaqueta como un chunk aparte sin
// plugins ni archivos .wasm sueltos, y no frena la primera pintura. A.init rechaza sin WebGL2.
import { useEffect, useRef, useState } from 'react'
import type { Aladin, AladinStatic, Catalog, GraphicOverlay } from 'aladin-lite'
import { useT } from '../../i18n'
import { formatDec, formatRA } from '../../lib/sky'
import { useView } from '../../state/view'
import ExternalLinks from './ExternalLinks'
import { useCurrentPosition } from './position'
import { contextFov, fovCorners, useTargets } from './targets'
import './nav.css'

// HiPS servidos por el espejo de IRSA (los mismos de CDS: ivo://CDS/P/2MASS/color, etc., según
// https://irsa.ipac.caltech.edu/data/hips/list). Se usa la URL y no el id de CDS porque los
// servidores alasky de CDS no respondieron desde nuestra red (11/11), e IRSA es además de donde
// salen los datos de SPHEREx: si IRSA anda, el contexto anda.
const IRSA_HIPS = 'https://irsa.ipac.caltech.edu/data/hips/CDS'
const SURVEYS = [
  { id: `${IRSA_HIPS}/2MASS/Color`, label: '2MASS' },
  { id: `${IRSA_HIPS}/AllWISE/RGB-W4-W2-W1`, label: 'AllWISE' },
  { id: `${IRSA_HIPS}/DSS2/color`, label: 'DSS2' },
] as const
type SurveyId = (typeof SURVEYS)[number]['id']
const SURVEY_KEY = 'spherex.nav.survey'

function storedSurvey(): SurveyId {
  try {
    const s = localStorage.getItem(SURVEY_KEY)
    if (SURVEYS.some(x => x.id === s)) return s as SurveyId
  } catch { /* sin localStorage */ }
  return SURVEYS[0].id
}

/** Colores de index.css (Aladin dibuja en canvas: necesita el valor, no la variable). */
function cssVar(name: string, fallback: string): string {
  try { return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback } catch { return fallback }
}

interface Live { A: AladinStatic; aladin: Aladin; box: GraphicOverlay; posCat: Catalog; j2kCat: Catalog; survey: string }

export default function SkyContext() {
  const t = useT()
  const { view, setView } = useView()
  const { list } = useTargets()
  const pos = useCurrentPosition(list)

  const hostRef = useRef<HTMLDivElement>(null)
  const live = useRef<Live | null>(null)
  // última posición conocida, para crear Aladin ya centrado (sin pasar por "0 +0")
  const [survey, setSurvey] = useState<SurveyId>(storedSurvey)
  const initial = useRef({ pos, fov: view.fov, survey })
  useEffect(() => { initial.current = { pos, fov: view.fov, survey } })

  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [reason, setReason] = useState('')
  const [picked, setPicked] = useState<{ ra: number; dec: number } | null>(null)

  // 1) una sola instancia, creada perezosamente al montar
  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    let cancelled = false
    ;(async () => {
      try {
        const A = (await import('aladin-lite')).default
        await A.init
        if (cancelled) return
        const { pos: p, fov, survey: sv } = initial.current
        const aladin = A.aladin(host, {
          survey: sv,
          fov: contextFov(fov),
          target: p ? `${p.ra} ${p.dec}` : '0 +0',
          cooFrame: 'ICRS',
          projection: 'TAN',
          showReticle: false,
          showLayersControl: false,
          showProjectionControl: false,
          showFrame: false,
          showFov: true,
          showCooLocation: true,
          showStatusBar: false,
          showContextMenu: false,
          showSimbadPointerControl: false,
          showSettingsControl: false,
          showShareControl: false,
          showFullscreenControl: true,
          showZoomControl: true,
          log: false, // no mandar estadísticas de uso a CDS
          samp: false,
          backgroundColor: cssVar('--bg', '#0b0f17'),
        })
        const box = A.graphicOverlay({ name: 'SPHEREx', color: cssVar('--accent', '#7cc4ff'), lineWidth: 2 })
        aladin.addOverlay(box)
        const j2kCat = A.catalog({ name: 'J2000', color: cssVar('--muted', '#8d97ad'), sourceSize: 14, shape: 'circle' })
        const posCat = A.catalog({ name: 'SPHEREx position', color: cssVar('--accent-2', '#ffb86b'), sourceSize: 18, shape: 'plus' })
        aladin.addCatalog(j2kCat)
        aladin.addCatalog(posCat)
        aladin.on('click', e => {
          if (e.isDragging || !Number.isFinite(e.ra) || !Number.isFinite(e.dec)) return
          setPicked({ ra: e.ra, dec: e.dec })
        })
        live.current = { A, aladin, box, posCat, j2kCat, survey: sv }
        setStatus('ready')
      } catch (e) {
        if (cancelled) return
        setReason(e instanceof Error ? e.message : String(e))
        setStatus('error')
      }
    })()
    return () => {
      cancelled = true
      live.current = null
      host.replaceChildren() // Aladin no trae destroy(): se suelta el canvas y sus nodos
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 2) sincronizar centro, campo, rectángulo y marcadores con la vista
  const ra = pos?.ra, dec = pos?.dec, tg = pos?.target ?? null
  useEffect(() => {
    const s = live.current
    if (status !== 'ready' || !s || ra == null || dec == null) return
    try {
      s.aladin.gotoRaDec(ra, dec)
      s.aladin.setFoV(contextFov(view.fov))
      s.box.removeAll()
      s.box.addFootprints([s.A.polygon(fovCorners(ra, dec, view.fov))])
      s.posCat.removeAll()
      s.posCat.addSources([s.A.source(ra, dec, { name: tg?.name ?? 'SPHEREx' })])
      s.j2kCat.removeAll()
      if (tg?.pmRequired) s.j2kCat.addSources([s.A.source(tg.j2000.ra, tg.j2000.dec, { name: `${tg.name} J2000` })])
    } catch (e) {
      console.warn('[nav] Aladin no pudo actualizar la vista', e)
    }
  }, [status, ra, dec, view.fov, tg])

  // 3) relevamiento
  useEffect(() => {
    try { localStorage.setItem(SURVEY_KEY, survey) } catch { /* */ }
    const s = live.current
    if (status !== 'ready' || !s || s.survey === survey) return
    s.survey = survey
    try { s.aladin.setImageSurvey(survey) } catch (e) { console.warn('[nav] relevamiento', survey, e) }
  }, [status, survey])

  // el click ofrecido se descarta si la vista cambió por otro lado
  const posKey = `${ra},${dec}`
  const [pickedFor, setPickedFor] = useState(posKey)
  if (pickedFor !== posKey) { setPickedFor(posKey); if (picked) setPicked(null) }

  return (
    <div className="nav-sky">
      <div className="nav-sky-head">
        <h2>{t('nav.sky.title')}</h2>
        {status !== 'error' && (
          <div className="seg nav-sky-surveys" role="group" aria-label={t('nav.sky.survey')}>
            {SURVEYS.map(s => (
              <button key={s.id} type="button" className={survey === s.id ? 'on' : ''} aria-pressed={survey === s.id}
                onClick={() => setSurvey(s.id)}>{s.label}</button>
            ))}
          </div>
        )}
      </div>

      <div className={`nav-sky-frame${status === 'error' ? ' failed' : ''}`}>
        <div ref={hostRef} className="nav-sky-host" />
        {status === 'loading' && <div className="nav-sky-placeholder muted" role="status">{t('nav.sky.loading')}</div>}
      </div>

      {status === 'error' && (
        <>
          <p className="notice error">{t('nav.sky.failed', { reason: reason || '?' })}</p>
          <ExternalLinks pos={pos} fov={view.fov} />
        </>
      )}

      {status === 'ready' && (
        <>
          <ul className="nav-legend">
            <li><span className="sw box" />{t('nav.sky.legend.box')}</li>
            <li><span className="sw pos" />{t('nav.sky.legend.pos')}</li>
            {tg?.pmRequired && <li><span className="sw j2k" />{t('nav.sky.legend.j2000')}</li>}
          </ul>
          {tg?.pmRequired && <p className="nav-help muted">{t('nav.sky.epochNote', { name: tg.name })}</p>}
          {picked ? (
            <div className="notice info nav-picked" aria-live="polite">
              <span className="mono">{t('nav.sky.clicked', { ra: formatRA(picked.ra), dec: formatDec(picked.dec) })}</span>
              <div className="nav-picked-actions">
                <button type="button" className="primary" onClick={() => { setView({ target: null, ra: picked.ra, dec: picked.dec }); setPicked(null) }}>
                  {t('nav.sky.goHere')}
                </button>
                <button type="button" onClick={() => setPicked(null)}>{t('nav.sky.dismiss')}</button>
              </div>
            </div>
          ) : <p className="nav-help muted">{t('nav.sky.clickHint')}</p>}
          <p className="nav-credit muted">{t('nav.sky.credit')}</p>
        </>
      )}
    </div>
  )
}
