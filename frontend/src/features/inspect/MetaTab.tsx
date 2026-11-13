// Pestaña Metadata (C6): de cuándo, con qué y cómo es el cuadro actual, y por qué tiene la calidad que tiene.
import type { ReactNode } from 'react'
import type { Frame, FrameMeta, Quality } from '../../api/types'
import { useT } from '../../i18n'
import { useView } from '../../state/view'
import {
  fmtCollection, fmtDateUtc, fmtNum, fmtPct, qualityReasons, readExtras, resolvingPower,
  type Lang, type QualityReason,
} from './logic'
import { UndocumentedAlarm } from './parts'
import type { T } from './text'

const QUALITY_CLASS: Record<Quality, string> = { ok: 'ok', suspect: 'warn', bad: 'bad' }

function reasonText(t: T, r: QualityReason, lang: Lang): string {
  switch (r.key) {
    case 'outside': return t('inspect.quality.reason.outside')
    case 'l2_qa': return t('inspect.quality.reason.l2_qa', { value: r.value })
    case 'target_masked': return t('inspect.quality.reason.target_masked', { bits: r.bits.join(', ') })
    case 'over_half': return t('inspect.quality.reason.over_half', { pct: fmtPct(r.fraction, lang) })
  }
}

function QualityBlock({ quality, reasons }: { quality: Quality | null; reasons: QualityReason[] }) {
  const t = useT()
  const { view } = useView()
  const q = quality ?? 'unknown'
  return (
    <div className={`ins-quality q-${q}`}>
      <div className="ins-quality-head">
        <span className="muted">{t('inspect.quality')}</span>
        <span className={`badge ${quality ? QUALITY_CLASS[quality] : ''}`}>{t(`inspect.quality.${q}`)}</span>
      </div>
      {quality && <p>{t(`inspect.quality.${quality}Why`)}</p>}
      {quality && quality !== 'ok' && reasons.length > 0 && (
        <ul>{reasons.map(r => <li key={r.key}>{reasonText(t, r, view.lang)}</li>)}</ul>
      )}
    </div>
  )
}

function Row({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{children}{hint && <span className="ins-hint">{hint}</span>}</dd>
    </>
  )
}

export default function MetaTab({ frame, meta }: { frame: Frame; meta: FrameMeta }) {
  const t = useT()
  const { view } = useView()
  const lang = view.lang
  const x = readExtras(meta)
  const quality = meta.quality ?? frame.quality ?? null
  const r = resolvingPower(meta.wavelength_um, meta.bandwidth_um)
  const xy = x.target?.xy ?? frame.target_xy
  const flagged = x.flagged_fraction ?? frame.flagged_fraction
  const band = meta.band ?? frame.band

  return (
    <div className="ins-meta">
      <UndocumentedAlarm bits={meta.flags.undocumented_bits_present} />
      <QualityBlock quality={quality} reasons={qualityReasons(meta, x)} />
      <dl className="ins-dl">
        <Row label={t('inspect.meta.dateUtc')}><span className="mono">{fmtDateUtc(meta.date)}</span></Row>
        <Row label={t('inspect.meta.mjd')}><span className="mono">{fmtNum(meta.mjd, 5, lang)}</span></Row>
        <Row label={t('inspect.meta.detector')}>
          <span className="ins-det" style={{ color: `var(--${meta.detector.toLowerCase()})` }}>{meta.detector}</span>
        </Row>
        <Row label={t('inspect.meta.band')}><span className="mono">{band ?? '—'}</span></Row>
        <Row label={t('inspect.meta.wavelength')} hint={r != null ? t('inspect.meta.wavelengthHint', { r }) : undefined}>
          <span className="mono">
            {t('inspect.meta.wavelengthValue', { lambda: fmtNum(meta.wavelength_um, 4, lang), width: fmtNum(meta.bandwidth_um, 4, lang) })}
          </span>
        </Row>
        <Row label={t('inspect.meta.exposure')}><span className="mono">{fmtNum(meta.exposure_s, 1, lang)} s</span></Row>
        <Row label={t('inspect.meta.release')}><span className="mono">{meta.release}</span></Row>
        <Row label={t('inspect.meta.collection')}>{fmtCollection(meta.collection ?? frame.collection)}</Row>
        <Row label={t('inspect.meta.psf')}>
          {meta.psf_fwhm_arcsec != null
            ? <span className="mono">{fmtNum(meta.psf_fwhm_arcsec, 2, lang)}″</span>
            : <span className="muted">{t('inspect.meta.notAvailable')}</span>}
        </Row>
        {x.shape && <Row label={t('inspect.meta.cutout')}><span className="mono">{x.shape[1]}×{x.shape[0]} px</span></Row>}
        {frame.fits_url && (
          <Row label={t('inspect.meta.fits')} hint={t('inspect.meta.fitsHint')}>
            <a href={frame.fits_url} download rel="noreferrer">{t('inspect.meta.fitsDownload')}</a>
          </Row>
        )}
        <Row label={t('inspect.meta.target')}>
          {x.target?.inside === false
            ? <span className="badge bad">{t('inspect.meta.targetOutside')}</span>
            : xy ? <span className="mono">x {fmtNum(xy[0], 1, lang)}, y {fmtNum(xy[1], 1, lang)} px</span> : '—'}
        </Row>
        {flagged != null && (
          <Row label={t('inspect.meta.flagged')}>{t('inspect.meta.flaggedValue', { pct: fmtPct(flagged, lang) })}</Row>
        )}
        {x.dqa && <Row label={t('inspect.meta.dqa')}><span className="mono">{x.dqa.l1 ?? '—'} / {x.dqa.l2 ?? '—'}</span></Row>}
        <Row label={t('inspect.meta.ctype')}><span className="mono">{meta.wcs.ctype.join(' · ')}</span></Row>
        <Row label={t('inspect.meta.crval')} hint={t('inspect.meta.crvalHint')}>
          <span className="mono">{fmtNum(meta.wcs.crval[0], 5, lang)}°, {fmtNum(meta.wcs.crval[1], 5, lang)}°</span>
        </Row>
      </dl>
    </div>
  )
}
