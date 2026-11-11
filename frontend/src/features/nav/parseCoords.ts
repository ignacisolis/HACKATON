// Parser de coordenadas ICRS, puro y sin dependencias (tests en parseCoords.test.ts).
//
// Acepta grados decimales y sexagesimal en sus variantes comunes:
//   RA  (horas por defecto si es sexagesimal): 133.795 · 08h55m10.831s · 08:55:10.831 · 08 55 10.831
//                                              8.919h (horas decimales) · 133d47m42s (grados sexagesimales)
//   Dec (siempre grados):                       -7.245 · -07d14m42.53s · -07:14:42.53 · -7 14 42.53 · −07°14′42.53″
//
// La trampa clásica: "-00:30:00". Si se toma el signo del primer componente (parseFloat("-00") = -0)
// y se suman los minutos, sale +0.5°. Acá el signo se lee del texto y se aplica al valor entero.

export type CoordError = 'empty' | 'format' | 'range' | 'minsec'
export type CoordResult = { ok: true; deg: number } | { ok: false; error: CoordError }
export type PairResult =
  | { ok: true; ra: number; dec: number; raText: string; decText: string }
  | { ok: false; error: CoordError; which: 'ra' | 'dec' }

interface Part { num: string; unit: string }

/** Unifica signos menos, comillas y primas tipográficas; minúsculas; sin espacios en los bordes. */
export function normalizeCoordText(s: string): string {
  return s
    .replace(/[−‒–—﹣－]/g, '-') // −, ‒, –, —, ﹣, －
    .replace(/[′’´]/g, "'")                   // ′, ’, ´
    .replace(/[″”]|''/g, '"')                     // ″, ”, ''
    .replace(/[º˚]/g, '°')                          // º, ˚
    .replace(/ /g, ' ')
    .trim()
    .toLowerCase()
}

const TOKEN = /\s*(\d+(?:\.\d*)?|\.\d+)\s*([hdms°'":])?\s*/y

/** Separa "08h55m10.831s" en [{08,h},{55,m},{10.831,s}]. null si sobra algo que no es número/unidad. */
function tokenize(rest: string): Part[] | null {
  const parts: Part[] = []
  TOKEN.lastIndex = 0
  while (TOKEN.lastIndex < rest.length) {
    const at = TOKEN.lastIndex
    const m = TOKEN.exec(rest)
    if (!m || TOKEN.lastIndex === at) return null
    parts.push({ num: m[1], unit: m[2] ?? '' })
  }
  return parts
}

const UNIT_OK: string[][] = [
  ['', 'h', 'd', '°', ':'], // 1er componente
  ['', 'm', "'", ':'],      // 2do
  ['', 's', '"'],           // 3ro
]

interface Parsed { sign: 1 | -1; explicitSign: boolean; value: number; kind: 'hours' | 'degrees' | 'unknown'; sexagesimal: boolean }

function parseCommon(input: string): Parsed | CoordError {
  let s = normalizeCoordText(input)
  if (!s) return 'empty'
  // coma decimal ("133,795") solo cuando es un único número: si no, la coma separa RA y Dec
  if (/^[+-]?\s*\d+,\d+$/.test(s)) s = s.replace(',', '.')
  const sm = /^([+-])?\s*(.*)$/.exec(s)!
  const sign: 1 | -1 = sm[1] === '-' ? -1 : 1
  const parts = tokenize(sm[2])
  if (!parts || parts.length === 0 || parts.length > 3) return 'format'
  const units = parts.map(p => p.unit)
  for (let i = 0; i < parts.length; i++) if (!UNIT_OK[i].includes(units[i])) return 'format'
  if (units[parts.length - 1] === ':') return 'format'
  const hasH = units.includes('h'), hasD = units.includes('d') || units.includes('°')
  if (hasH && hasD) return 'format'
  // solo el último componente puede tener decimales
  for (let i = 0; i < parts.length - 1; i++) if (parts[i].num.includes('.')) return 'format'
  const n = parts.map(p => Number(p.num))
  if (n.some(x => !Number.isFinite(x))) return 'format'
  if (n.slice(1).some(x => x >= 60)) return 'minsec'
  const value = n[0] + (n[1] ?? 0) / 60 + (n[2] ?? 0) / 3600
  return {
    sign, explicitSign: sm[1] != null, value,
    kind: hasH ? 'hours' : hasD ? 'degrees' : 'unknown',
    sexagesimal: parts.length > 1,
  }
}

/** RA → grados [0, 360). Sexagesimal sin unidades se lee en horas; un solo número, en grados. */
export function parseRA(input: string): CoordResult {
  const p = parseCommon(input)
  if (typeof p === 'string') return { ok: false, error: p }
  if (p.sign < 0 && p.value !== 0) return { ok: false, error: 'range' }
  const hours = p.kind === 'hours' || (p.kind === 'unknown' && p.sexagesimal)
  if (hours) {
    if (p.value >= 24) return { ok: false, error: 'range' }
    return { ok: true, deg: p.value * 15 }
  }
  if (p.value >= 360) return { ok: false, error: 'range' }
  return { ok: true, deg: p.value }
}

/** Dec → grados [−90, +90]. Siempre en grados; una 'h' es error. */
export function parseDec(input: string): CoordResult {
  const p = parseCommon(input)
  if (typeof p === 'string') return { ok: false, error: p }
  if (p.kind === 'hours') return { ok: false, error: 'format' }
  if (p.value > 90) return { ok: false, error: 'range' }
  const deg = p.sign * p.value
  return { ok: true, deg: deg === 0 ? 0 : deg } // sin -0
}

/**
 * Parte un texto con RA y Dec juntas: "08h55m10.831s -07d14m42.53s", "133.795 -7.245",
 * "133.795, -7.245", "08 55 10.8 07 14 42". null si no se puede partir en dos coordenadas válidas.
 */
export function splitPair(input: string): [string, string] | null {
  const s = normalizeCoordText(input)
  if (!s) return null
  const valid = (a: string, b: string) => parseRA(a).ok && parseDec(b).ok
  const candidates: [string, string][] = []
  // 1) coma separadora (una sola)
  const commas = s.split(',')
  if (commas.length === 2) candidates.push([commas[0].trim(), commas[1].trim()])
  // 2) un signo después del comienzo: ahí empieza la Dec
  const i = s.slice(1).search(/[+-]/)
  if (i >= 0) candidates.push([s.slice(0, i + 1).trim(), s.slice(i + 1).trim()])
  // 3) sin signo: mitad y mitad de los grupos separados por espacios (1+1, 2+2, 3+3)
  const toks = s.split(/\s+/)
  if (toks.length % 2 === 0 && toks.length <= 6) {
    const h = toks.length / 2
    candidates.push([toks.slice(0, h).join(' '), toks.slice(h).join(' ')])
  }
  for (const [a, b] of candidates) if (a && b && valid(a, b)) return [a, b]
  return null
}

/**
 * Para el pegado en el campo RA: devuelve [ra, dec] solo si el texto NO es una RA válida por sí
 * sola y sí se puede partir en dos. "08 55" es 08h55m (RA sola), no RA 8° + Dec 55°.
 */
export function splitIfPair(input: string): [string, string] | null {
  return parseRA(input).ok ? null : splitPair(input)
}

/**
 * Lo que hace el formulario al enviar. Si la Dec está vacía y en el campo RA vinieron las dos,
 * las reparte. Si RA es una sola coordenada válida, se usa tal cual (y falta la Dec).
 */
export function parseCoordInputs(raText: string, decText: string): PairResult {
  const decEmpty = !normalizeCoordText(decText)
  if (decEmpty) {
    const pair = splitIfPair(raText)
    if (pair) {
      const ra = parseRA(pair[0]), dec = parseDec(pair[1])
      if (ra.ok && dec.ok) return { ok: true, ra: ra.deg, dec: dec.deg, raText: pair[0], decText: pair[1] }
    }
  }
  const ra = parseRA(raText)
  if (!ra.ok) return { ok: false, error: ra.error, which: 'ra' }
  const dec = parseDec(decText)
  if (!dec.ok) return { ok: false, error: dec.error, which: 'dec' }
  return { ok: true, ra: ra.deg, dec: dec.deg, raText: raText.trim(), decText: decText.trim() }
}
