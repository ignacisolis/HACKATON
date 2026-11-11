// Tipos mínimos de aladin-lite 3.9.x (el paquete npm no trae .d.ts). Solo lo que usa SkyContext.
// Referencia: https://cds-astro.github.io/aladin-lite/ (API v3).
declare module 'aladin-lite' {
  export interface AladinOptions {
    survey?: string
    fov?: number
    target?: string
    cooFrame?: 'ICRS' | 'ICRSd' | 'galactic'
    projection?: string
    showReticle?: boolean
    showZoomControl?: boolean
    showLayersControl?: boolean
    showFullscreenControl?: boolean
    showProjectionControl?: boolean
    showFrame?: boolean
    showCooLocation?: boolean
    showFov?: boolean
    showStatusBar?: boolean
    showContextMenu?: boolean
    showSimbadPointerControl?: boolean
    showCooGridControl?: boolean
    showSettingsControl?: boolean
    showShareControl?: boolean
    /** manda estadísticas de uso a CDS; por defecto true */
    log?: boolean
    samp?: boolean
    backgroundColor?: string
    inertia?: boolean
  }

  export interface ClickEvent { ra: number; dec: number; x: number; y: number; isDragging?: boolean }

  export interface Shape { readonly __shape: unique symbol }

  export interface GraphicOverlay {
    add(shape: Shape): void
    addFootprints(shapes: Shape[]): void
    removeAll(): void
  }

  export interface Source { readonly __source: unique symbol }

  export interface Catalog {
    addSources(sources: Source | Source[]): void
    removeAll(): void
  }

  export interface Aladin {
    gotoRaDec(ra: number, dec: number): void
    setFoV(fovDeg: number): void
    getRaDec(): [number, number]
    setImageSurvey(id: string): void
    addOverlay(o: GraphicOverlay): void
    addCatalog(c: Catalog): void
    on(event: 'click', cb: (e: ClickEvent) => void): void
    on(event: string, cb: (...args: unknown[]) => void): void
  }

  interface ShapeOptions { color?: string; lineWidth?: number; lineDash?: number[]; fillColor?: string; opacity?: number }

  export interface AladinStatic {
    /** promesa que resuelve cuando el WebAssembly está listo; rechaza sin WebGL2 */
    init: Promise<void>
    aladin(el: HTMLElement | string, opts?: AladinOptions): Aladin
    graphicOverlay(opts?: { name?: string; color?: string; lineWidth?: number; lineDash?: number[] }): GraphicOverlay
    polygon(points: [number, number][], opts?: ShapeOptions): Shape
    circle(ra: number, dec: number, radiusDeg: number, opts?: ShapeOptions): Shape
    catalog(opts?: { name?: string; color?: string; sourceSize?: number; shape?: string }): Catalog
    source(ra: number, dec: number, data?: Record<string, unknown>): Source
  }

  const A: AladinStatic
  export default A
}
