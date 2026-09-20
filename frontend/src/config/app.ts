export type VtuberMode = 'multi' | 'single'

function resolveVtuberMode(value: string | undefined): VtuberMode {
  return value === 'single' ? 'single' : 'multi'
}

export const appConfig = Object.freeze({
  vtuberMode: resolveVtuberMode(import.meta.env.VITE_VTUBER_MODE),
  defaultVtuberId: import.meta.env.VITE_DEFAULT_VTUBER_ID?.trim() || undefined,
})

export const isMultiVtuberMode = appConfig.vtuberMode === 'multi'
