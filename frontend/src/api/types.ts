// Tipos de la API HTTP. Fuente de verdad: contracts/api.md (v0) + decisiones del backend.
// Si el contrato cambia, se cambia acá y en ningún otro lado.

export type Detector = 'D1' | 'D2' | 'D3' | 'D4' | 'D5' | 'D6'
export const DETECTORS: Detector[] = ['D1', 'D2', 'D3', 'D4', 'D5', 'D6']

export type Quality = 'ok' | 'suspect' | 'bad'
export type TargetKey = 'eps_ind_b' | 'wise_0855' | 'rw_aur' | 'r_dra'

/** Qué se le pide al backend: un objetivo de la demo (aplica movimiento propio) o una posición libre. */
export type SkyQuery =
  | { target: TargetKey; size?: number }
  | { ra: number; dec: number; size?: number }

export interface QueryEcho {
  ra: number
  dec: number
  size: number
  target?: TargetKey | null
  resolved_from?: string
  coord_epoch_applied?: string
  band?: number | null
  detector?: Detector | null
}

export interface Frame {
  id: string
  mjd: number
  /** ISO 8601 UTC, sin zona */
  date: string
  detector: Detector
  /** λ en la posición del objetivo. null mientras ready=false */
  wavelength_um: number | null
  bandwidth_um: number | null
  band: number | null
  release: string
  collection?: string
  image_url: string
  meta_url?: string
  /** recorte FITS original (MEF) de IRSA; el backend responde 302. Opcional */
  fits_url?: string
  /** píxeles del PNG, base 0, x a la derecha, y hacia abajo. Cambia de cuadro a cuadro */
  target_xy: [number, number] | null
  flagged_fraction: number | null
  quality: Quality | null
  /** false = todavía no se bajó de IRSA (carga progresiva) */
  ready?: boolean
}

export interface FramesResponse {
  query: QueryEcho
  release?: { collections: string[]; label: string }
  n_frames: number
  n_dates: number
  pending?: number
  queued?: number
  complete?: boolean
  offset?: number
  limit?: number | null
  frames: Frame[]
}

export interface FlagCount {
  bit: number
  name: string
  label: string
  pixels: number
  fraction: number
}

export interface FrameMeta {
  id: string
  mjd: number
  date: string
  detector: Detector
  release: string
  collection?: string
  exposure_s: number
  wavelength_um: number
  bandwidth_um: number
  band?: number
  wcs: { crval: [number, number]; ctype: [string, string] }
  flags: {
    extension_is_mask: boolean
    /** Del recorte: lo que se muestra */
    cutout_counts: FlagCount[]
    /** De la exposición entera (2040×2040): NO mezclar con cutout_counts */
    full_frame_counts: Record<string, number>
    undocumented_bits_present: number[]
    at_target?: string[]
  }
  mask_layers: string[]
  quality?: Quality
  /** extra del backend (decisión 10): dónde cae el objetivo en este recorte */
  target?: { key: string; radec: [number, number]; xy: [number, number]; inside: boolean; value?: number; variance?: number; zodi?: number }
  psf_fwhm_arcsec?: number
  flagged_fraction?: number
  dqa?: { l1: string; l2: string }
  bunit?: string
  /** [alto, ancho] del recorte en píxeles */
  shape?: [number, number]
}

export interface SpectrumPoint {
  wavelength_um: number
  bandwidth_um: number
  band: number
  flux: number
  flux_err: number
  unit: string
  detector: Detector
  n_epochs: number
  flagged_fraction: number
  quality: Quality
}

export interface SpectrumResponse {
  query: QueryEcho
  aperture_px: number
  mask_purpose: string
  n_points: number
  n_epochs_used: number
  points: SpectrumPoint[]
}

export interface LightCurveResponse {
  mjds: number[]
  flux: number[]
  flux_err: number[]
}

export interface TargetSummary {
  key: TargetKey
  name: string
  ra: number
  dec: number
  size: number
  coord_epoch_applied?: string
  frames_url?: string
  view_query?: string
  frames?: number | null
  cached?: number
  failed?: unknown[]
}

export interface CoverageResponse {
  query: QueryEcho
  total: number
  detectors: Partial<Record<Detector, number>>
  collections: Record<string, number>
  dates: { date: string; count: number; detectors: Detector[] }[]
}

export interface ApiErrorBody {
  error: string
  detail: string
}

export type Stretch = 'asinh' | 'linear'
export type ImageLayer = 'image' | 'image-zodi' | 'variance' | 'flags'

export interface ImageOptions {
  layer?: ImageLayer
  stretch?: Stretch
  vmin?: number
  vmax?: number
  /** nombres o números de bits de FLAGS (solo layer=flags) */
  bits?: string[]
}
