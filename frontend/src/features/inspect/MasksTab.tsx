// Pestaña Máscaras (C6, "máscaras de contaminación"): cuentas de FLAGS del RECORTE y un interruptor
// por capa que escribe view.mask (el reproductor la dibuja con layer=flags&bits=). Las cuentas de la
// exposición completa van aparte y colapsadas: mezclarlas con las del recorte miente por órdenes de magnitud.
import { useId } from 'react'
import type { FrameMeta } from '../../api/types'
import { useT } from '../../i18n'
import { useView } from '../../state/view'
import { bitInfo, canonicalName, FULL_FRAME_PIXELS, fullFrameRows, groupCounts, targetLayers, toggleMask } from './bits'
import { cutoutPixels, fmtInt, fmtPct } from './logic'
import { UndocumentedAlarm } from './parts'
import { bitDescription } from './text'

export default function MasksTab({ meta }: { meta: FrameMeta }) {
  const t = useT()
  const { view, setView } = useView()
  const lang = view.lang
  const id = useId()
  const layers = meta.mask_layers
  const active = view.mask
  const atTarget = meta.flags.at_target
  const tl = targetLayers(atTarget, layers)
  const groups = groupCounts(meta.flags.cutout_counts)
  const n = cutoutPixels(meta)
  const elsewhere = active.filter(a => !layers.includes(a))
  const hasSource = meta.flags.cutout_counts.some(c => canonicalName(c.name) === 'SOURCE')
  const full = fullFrameRows(meta.flags.full_frame_counts)
  const onlyTarget = tl.length > 0 && tl.length === active.length && tl.every(l => active.includes(l))

  return (
    <div className="ins-masks">
      <UndocumentedAlarm bits={meta.flags.undocumented_bits_present} />
      <p className="ins-lead">{n ? t('inspect.masks.intro', { n: fmtInt(n, lang) }) : t('inspect.masks.introNoN')}</p>

      <div className="ins-actions" role="group" aria-label={t('inspect.masks.actions')}>
        <button type="button" onClick={() => setView({ mask: [] })} disabled={!active.length}>{t('inspect.masks.none')}</button>
        {atTarget && (
          <button type="button" onClick={() => setView({ mask: tl })} disabled={!tl.length} aria-pressed={onlyTarget}>
            {t('inspect.masks.atTarget')}
          </button>
        )}
      </div>
      {atTarget && (
        <p className="ins-hint">
          {atTarget.length ? t('inspect.masks.atTargetHint', { bits: atTarget.join(', ') }) : t('inspect.masks.atTargetNone')}
        </p>
      )}
      {elsewhere.length > 0 && <p className="notice info">{t('inspect.masks.activeElsewhere', { names: elsewhere.join(', ') })}</p>}

      {groups.length === 0 ? <p className="muted">{t('inspect.masks.empty')}</p> : (
        <table className="ins-table">
          <colgroup><col /><col className="c-bit" /><col className="c-px" /><col className="c-pct" /></colgroup>
          <thead>
            <tr>
              <th scope="col">{t('inspect.masks.col.layer')}</th>
              <th scope="col" className="num">{t('inspect.masks.col.bit')}</th>
              <th scope="col" className="num">{t('inspect.masks.col.pixels')}</th>
              <th scope="col" className="num">{t('inspect.masks.col.pct')}</th>
            </tr>
          </thead>
          {groups.map(g => (
            <tbody key={g.group}>
              <tr className={`ins-group g-${g.group}`}>
                <th scope="colgroup" colSpan={4}>
                  {t(`inspect.masks.group.${g.group}`)}
                  <span className="ins-hint">{t(`inspect.masks.group.${g.group}Hint`)}</span>
                </th>
              </tr>
              {g.rows.map(r => {
                const offered = layers.includes(r.name)
                const on = active.includes(r.name)
                const info = bitInfo(r.name, r.bit)
                const inputId = `${id}-${r.name}`
                return (
                  <tr key={r.name} className={on ? 'on' : ''}>
                    <td>
                      <div className="ins-layer">
                        <input id={inputId} type="checkbox" checked={on} disabled={!offered}
                          onChange={() => setView(v => ({ mask: toggleMask(v.mask, r.name) }))}
                          aria-label={t('inspect.masks.toggle', { name: r.name })}
                          title={offered ? undefined : t('inspect.masks.notLayer')} />
                        <label htmlFor={inputId} title={r.label}>
                          <span className="mono ins-name">{r.name}</span>
                          {atTarget?.includes(r.name) && <span className="badge warn ins-tag">{t('inspect.masks.targetBadge')}</span>}
                          {info?.deprecated && <span className="badge ins-tag">{t('inspect.masks.deprecated')}</span>}
                          <span className="ins-desc">{bitDescription(t, r.name, r.label)}</span>
                        </label>
                      </div>
                    </td>
                    <td className="num mono">{r.bit}</td>
                    <td className="num mono">{fmtInt(r.pixels, lang)}</td>
                    <td className="num mono">{fmtPct(r.fraction, lang)}</td>
                  </tr>
                )
              })}
            </tbody>
          ))}
        </table>
      )}

      {hasSource && <p className="notice info">{t('inspect.masks.sourceNote')}</p>}

      <details className="ins-full">
        <summary>{t('inspect.masks.fullTitle')}</summary>
        <p className="notice">{t('inspect.masks.fullNote')}</p>
        {full.length === 0 ? <p className="muted">{t('inspect.masks.fullEmpty')}</p> : (
          <table className="ins-table ins-table-full">
            <colgroup><col /><col className="c-px-full" /><col className="c-pct" /></colgroup>
            <thead>
              <tr>
                <th scope="col">{t('inspect.masks.col.layer')}</th>
                <th scope="col" className="num">{t('inspect.masks.col.pixels')}</th>
                <th scope="col" className="num">{t('inspect.masks.col.pctFull')}</th>
              </tr>
            </thead>
            <tbody>
              {full.map(r => (
                <tr key={r.name}>
                  <td className="mono">{r.name}</td>
                  <td className="num mono">{fmtInt(r.pixels, lang)}</td>
                  <td className="num mono">{fmtPct(r.pixels / FULL_FRAME_PIXELS, lang)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </details>
    </div>
  )
}
