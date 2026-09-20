export type VtuberMode = 'multi' | 'single'

export interface VtuberAppEnv {
  readonly VITE_VTUBER_MODE?: string
  readonly VITE_DEFAULT_VTUBER_ID?: string
}

export interface AppConfig {
  readonly vtuberMode: VtuberMode
  readonly defaultVtuberId?: string
}

export function resolveAppConfig(env: VtuberAppEnv): AppConfig {
  const modeValue = env.VITE_VTUBER_MODE
  if (modeValue !== undefined && modeValue !== 'multi' && modeValue !== 'single') {
    throw new Error(
      `[VTuber config] Invalid VITE_VTUBER_MODE "${modeValue}". Expected "multi" or "single".`,
    )
  }

  const vtuberMode = modeValue ?? 'multi'
  const defaultVtuberId = env.VITE_DEFAULT_VTUBER_ID?.trim() || undefined

  if (vtuberMode === 'single' && !defaultVtuberId) {
    throw new Error(
      '[VTuber config] VITE_DEFAULT_VTUBER_ID is required when VITE_VTUBER_MODE is "single".',
    )
  }

  return { vtuberMode, defaultVtuberId }
}

const clientEnv = (import.meta as ImportMeta & { readonly env?: VtuberAppEnv }).env

export const appConfig = Object.freeze(resolveAppConfig(clientEnv ?? {}))

export const isMultiVtuberMode = appConfig.vtuberMode === 'multi'
