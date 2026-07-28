// Base URL backend, dipakai bareng App & komponen lain (mis. DocumentsPanel).
// Prioritas: VITE_API_BASE_URL (override eksplisit) → build PRODUKSI = string
// kosong (same-origin, FE disajikan FastAPI di container) → dev = localhost:8000.
// `??` bukan `||` supaya "" (same-origin) tak jatuh ke fallback.
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.PROD ? '' : 'http://localhost:8000')
