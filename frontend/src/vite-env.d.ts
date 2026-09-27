/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ADMIN_SALON_ID?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
