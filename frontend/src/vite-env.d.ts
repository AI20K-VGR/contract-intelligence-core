/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_KEYCLOAK_URL?: string
  readonly VITE_KEYCLOAK_REALM?: string
  readonly VITE_KEYCLOAK_CLIENT_ID?: string
  /** 'true' để hiện chuông thông báo; BE chưa có API nên mặc định tắt. */
  readonly VITE_ENABLE_NOTIFICATIONS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
