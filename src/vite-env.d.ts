/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ALERT_API_TOKEN?: string;
  readonly VITE_DATA_SOURCE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
