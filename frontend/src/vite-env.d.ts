/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_DOC_ID: string
  readonly VITE_USER_ID: string
  readonly VITE_EMBED_MODE?: string
  readonly VITE_MOUNT_ID?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
