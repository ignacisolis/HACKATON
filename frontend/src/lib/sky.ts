// Utilidades de coordenadas, puras y testeadas (sky.test.ts).

/** Píxel del PNG (grilla norte arriba, este a la izquierda, centrada en ra0/dec0) → RA/Dec en grados.
 *  Aproximación tangente plana: vale para recortes de ≤0.3°. x a la derecha, y hacia abajo, base 0. */
export function pixelToSky(x: number, y: number, widthPx: number, heightPx: number,
  ra0: number, dec0: number, sizeDeg: number): { ra: number; dec: number } {
  const scale = sizeDeg / widthPx // grados por píxel
  const dx = x - (widthPx - 1) / 2
  const dy = y - (heightPx - 1) / 2
  const dec = dec0 - dy * scale
  const ra = ra0 - (dx * scale) / Math.cos((dec0 * Math.PI) / 180)
  return { ra: ((ra % 360) + 360) % 360, dec }
}

/** Inversa de pixelToSky. */
export function skyToPixel(ra: number, dec: number, widthPx: number, heightPx: number,
  ra0: number, dec0: number, sizeDeg: number): { x: number; y: number } {
  const scale = sizeDeg / widthPx
  let dra = ra - ra0
  if (dra > 180) dra -= 360
  if (dra < -180) dra += 360
  return {
    x: (widthPx - 1) / 2 - (dra * Math.cos((dec0 * Math.PI) / 180)) / scale,
    y: (heightPx - 1) / 2 - (dec - dec0) / scale,
  }
}

const pad = (n: number, w: number, d = 0) => n.toFixed(d).padStart(w + (d ? d + 1 : 0), '0')

export function formatRA(deg: number): string {
  let s = (((deg % 360) + 360) % 360) / 15 * 3600
  const h = Math.floor(s / 3600); s -= h * 3600
  const m = Math.floor(s / 60); s -= m * 60
  if (Number(s.toFixed(2)) >= 60) return formatRA(deg + 0.0000001)
  return `${pad(h, 2)}h${pad(m, 2)}m${pad(s, 2, 2)}s`
}

export function formatDec(deg: number): string {
  const sign = deg < 0 ? '−' : '+'
  let s = Math.abs(deg) * 3600
  const d = Math.floor(s / 3600); s -= d * 3600
  const m = Math.floor(s / 60); s -= m * 60
  return `${sign}${pad(d, 2)}°${pad(m, 2)}′${pad(s, 2, 1)}″`
}

/** MJD → Date (UTC). */
export const mjdToDate = (mjd: number) => new Date((mjd - 40587) * 86400000)
