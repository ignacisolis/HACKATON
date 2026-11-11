// Ayudas de texto sin componentes (separadas de parts.tsx para que Fast Refresh funcione).
import type { useT } from '../../i18n'
import dict from './i18n'

export type T = ReturnType<typeof useT>

/** Descripción traducida de un bit; si no está en el catálogo, la etiqueta que manda el backend. */
export function bitDescription(t: T, name: string, fallback: string): string {
  const key = `inspect.bit.${name.toUpperCase()}`
  return key in dict.en ? t(key) : fallback
}
