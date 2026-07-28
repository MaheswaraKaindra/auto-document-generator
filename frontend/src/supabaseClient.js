// Klien Supabase + jembatan token ke backend.
//
// Cermin backend: auth AKTIF hanya kalau dikonfigurasi (VITE_SUPABASE_URL +
// VITE_SUPABASE_ANON_KEY di frontend/.env.local). Kalau kosong, app jalan mode
// dev tanpa login — sama seperti backend saat SUPABASE_URL kosong. Jadi satu
// keputusan ("apakah auth dipasang") datang dari env, bukan flag tersebar.
import { createClient } from '@supabase/supabase-js'

// Dashboard kadang memberi URL berakhiran /rest/v1/. Auth SDK butuh base URL,
// jadi ekor yang umum salah-tempel dipangkas — konfigurasi tak jadi rapuh.
function normalizeUrl(raw) {
  if (!raw) return raw
  return raw.trim().replace(/\/(rest|auth)\/v1\/?$/, '').replace(/\/$/, '')
}

const url = normalizeUrl(import.meta.env.VITE_SUPABASE_URL)
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

// Satu-satunya sumber kebenaran "apakah harus login".
export const authEnabled = Boolean(url && anonKey)
export const supabase = authEnabled ? createClient(url, anonKey) : null

// Token akses terkini, dijaga sinkron lewat onAuthStateChange supaya `authHeader`
// bisa dibaca SINKRON di tiap fetch (tanpa await getSession tiap panggilan).
let accessToken = null
if (supabase) {
  supabase.auth.getSession().then(({ data }) => {
    accessToken = data.session?.access_token ?? null
  })
  supabase.auth.onAuthStateChange((_event, session) => {
    accessToken = session?.access_token ?? null
  })
}

// Header Authorization untuk request ke backend. Objek kosong saat mode dev /
// belum login — di-spread ke fetch tanpa efek, jadi call site tetap ringkas.
export function authHeader() {
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {}
}
