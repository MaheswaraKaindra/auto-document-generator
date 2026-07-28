// Gerbang login. Membungkus aplikasi: kalau auth dipasang (Supabase dikonfigurasi)
// dan belum login, tampilkan layar masuk; kalau tidak, teruskan apa adanya.
//
// Cermin backend: saat auth non-aktif (env kosong), gerbang ini transparan —
// app jalan seperti sebelum auth ada. Jadi memasang auth = mengisi env, bukan
// mengubah alur.
import { useEffect, useState } from 'react'
import { authEnabled, supabase } from './supabaseClient'
import './AuthGate.css'

function LoginScreen() {
  const [mode, setMode] = useState('signin') // 'signin' | 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true); setError(''); setMessage('')
    try {
      if (mode === 'signup') {
        const { error } = await supabase.auth.signUp({ email, password })
        if (error) throw error
        // Kalau project mewajibkan konfirmasi email, sesi belum aktif sampai
        // tautan diklik — beri tahu, jangan diam.
        setMessage('Akun dibuat. Cek email untuk konfirmasi bila diminta, lalu masuk.')
        setMode('signin')
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
        // Sukses: onAuthStateChange di App menukar tampilan ke aplikasi.
      }
    } catch (err) {
      setError(err.message || 'Gagal memproses. Coba lagi.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={submit}>
        <h1 className="auth-title">Auto Document Generator</h1>
        <p className="auth-sub">
          {mode === 'signin' ? 'Masuk untuk membuat dokumen' : 'Buat akun baru'}
        </p>

        <label className="auth-field">
          <span>Email</span>
          <input type="email" required value={email} autoComplete="email"
                 onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="auth-field">
          <span>Kata sandi</span>
          <input type="password" required minLength={6} value={password}
                 autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                 onChange={(e) => setPassword(e.target.value)} />
        </label>

        {error && <p className="auth-error">{error}</p>}
        {message && <p className="auth-message">{message}</p>}

        <button className="auth-submit" type="submit" disabled={busy}>
          {busy ? 'Memproses…' : mode === 'signin' ? 'Masuk' : 'Daftar'}
        </button>

        <button type="button" className="auth-toggle"
                onClick={() => { setMode(mode === 'signin' ? 'signup' : 'signin'); setError('') }}>
          {mode === 'signin' ? 'Belum punya akun? Daftar' : 'Sudah punya akun? Masuk'}
        </button>
      </form>
    </div>
  )
}

export default function AuthGate({ children }) {
  // Hooks dipanggil TANPA syarat (aturan hooks React); percabangan mode dev vs
  // aktif dilakukan SESUDAHNYA. `authEnabled` konstan module-level, jadi urutan
  // hook tak pernah berubah antar-render.
  const [session, setSession] = useState(null)
  const [ready, setReady] = useState(!authEnabled)  // mode dev: langsung siap

  useEffect(() => {
    if (!authEnabled) return undefined
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session); setReady(true)
    })
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s))
    return () => data.subscription.unsubscribe()
  }, [])

  // Auth non-aktif: gerbang transparan (mode dev) — sama seperti sebelum auth ada.
  if (!authEnabled) return children
  if (!ready) return <div className="auth-shell"><p className="auth-sub">Memuat…</p></div>
  if (!session) return <LoginScreen />

  return (
    <>
      <div className="auth-bar">
        <span className="auth-who">{session.user?.email}</span>
        <button className="auth-signout" onClick={() => supabase.auth.signOut()}>
          Keluar
        </button>
      </div>
      {children}
    </>
  )
}
