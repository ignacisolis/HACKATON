// i18n mínimo, sin dependencias. Cada área tiene su diccionario en features/<area>/i18n.ts
// (así nadie pisa el archivo de otro). Claves con prefijo de área: 'player.play', 'nav.go', …
// Uso: const t = useT(); t('player.frameOf', { i: 3, n: 40 })  →  "Frame 3 of 40"
import { useCallback } from 'react'
import { useView, type Lang } from '../state/view'
import common from './common'
import player from '../features/player/i18n'
import science from '../features/science/i18n'
import nav from '../features/nav/i18n'
import inspect from '../features/inspect/i18n'

export type Dict = Record<Lang, Record<string, string>>

const ALL: Dict[] = [common, player, science, nav, inspect]
const merged: Dict = { en: {}, es: {} }
for (const d of ALL) { Object.assign(merged.en, d.en); Object.assign(merged.es, d.es) }

export function translate(lang: Lang, key: string, vars?: Record<string, string | number>): string {
  let s = merged[lang][key] ?? merged.en[key]
  if (s == null) {
    if (import.meta.env.DEV) console.warn(`[i18n] falta la clave "${key}"`)
    return key
  }
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v))
  return s
}

export function useT() {
  const { view } = useView()
  return useCallback((key: string, vars?: Record<string, string | number>) => translate(view.lang, key, vars), [view.lang])
}

/** Para tests: claves que existen en un idioma y no en el otro. */
export function missingKeys(): { en: string[]; es: string[] } {
  return {
    en: Object.keys(merged.es).filter(k => !(k in merged.en)),
    es: Object.keys(merged.en).filter(k => !(k in merged.es)),
  }
}
