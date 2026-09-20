/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_VTUBER_MODE?: 'multi' | 'single'
  readonly VITE_DEFAULT_VTUBER_ID?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
