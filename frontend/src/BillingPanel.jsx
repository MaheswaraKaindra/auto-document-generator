import { useState, useEffect } from 'react'
import './BillingPanel.css'
import { API_BASE_URL } from './api'
import { authHeader } from './supabaseClient'

export default function BillingPanel() {
  const [usage, setUsage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [checkoutLoading, setCheckoutLoading] = useState(false)
  const [alertMsg, setAlertMsg] = useState(null)

  const fetchUsage = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE_URL}/billing/usage`, {
        headers: authHeader(),
      })
      if (!res.ok) {
        throw new Error(`Gagal memuat status kuota (${res.status})`)
      }
      const data = await res.json()
      setUsage(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchUsage()

    // Periksa apakah ada callback dari Stripe checkout
    const params = new URLSearchParams(window.location.search)
    if (params.get('billing') === 'success') {
      // Kembali dari Stripe TIDAK sama dengan tier sudah naik: yang menaikkan tier
      // adalah webhook ber-signature sah, dan dia bisa mendarat beberapa detik
      // sesudah pengguna kembali ke sini. Mengumumkan "sudah Pro" di titik ini
      // berarti berbohong tiap kali webhook-nya telat — badge di panel yang sama
      // masih menulis "free". Jadi kalimatnya menyebut apa yang benar-benar sudah
      // terjadi, dan panelnya menyegarkan diri.
      setAlertMsg({
        type: 'success',
        text: 'Pembayaran diterima Stripe. Tier akan naik ke Pro begitu konfirmasi '
          + 'langganan masuk (biasanya beberapa detik) — muat ulang halaman kalau '
          + 'badge di atas masih menulis "free".',
      })
      window.history.replaceState({}, document.title, window.location.pathname)
    } else if (params.get('billing') === 'simulasi') {
      // Stripe belum dikonfigurasi di server. TIDAK ada pembayaran dan tier TIDAK
      // berubah — dan itu harus dikatakan, bukan dirayakan.
      setAlertMsg({
        type: 'warning',
        text: 'Mode simulasi: pembayaran Stripe belum aktif di server ini, jadi '
          + 'tier akun Anda TIDAK berubah. Pengelola perlu mengisi STRIPE_SECRET_KEY, '
          + 'STRIPE_WEBHOOK_SECRET, dan STRIPE_PRO_PRICE_ID.',
      })
      window.history.replaceState({}, document.title, window.location.pathname)
    } else if (params.get('billing') === 'cancel') {
      setAlertMsg({
        type: 'warning',
        text: 'Proses checkout Stripe dibatalkan.',
      })
      window.history.replaceState({}, document.title, window.location.pathname)
    }
  }, [])

  const handleUpgrade = async () => {
    setCheckoutLoading(true)
    try {
      const res = await fetch(`${API_BASE_URL}/billing/checkout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader(),
        },
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || 'Gagal memulai Stripe checkout')
      }
      const data = await res.json()
      // `is_stub` = server belum punya kredensial Stripe. Mengikuti checkout_url-nya
      // cuma memutar pengguna kembali ke halaman ini; katakan saja apa adanya di
      // tempat dia menekan tombolnya.
      if (data.is_stub) {
        setAlertMsg({
          type: 'warning',
          text: 'Pembayaran Stripe belum aktif di server ini, jadi upgrade tidak '
            + 'bisa diproses dan tier Anda tetap free. Hubungi pengelola aplikasi.',
        })
        return
      }
      if (data.checkout_url) {
        window.location.href = data.checkout_url
      }
    } catch (err) {
      alert(`Error: ${err.message}`)
    } finally {
      setCheckoutLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="panel">
        <h2 className="panel-title">Billing & Pemakaian Kuota</h2>
        <p className="hint">Memuat informasi kuota & pemakaian...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="panel">
        <h2 className="panel-title">Billing & Pemakaian Kuota</h2>
        <p className="error" style={{ color: '#f85149' }}>{error}</p>
        <button onClick={fetchUsage} className="btn-secondary" style={{ marginTop: '0.5rem' }}>
          Coba Lagi
        </button>
      </div>
    )
  }

  const { tier, limit, jobs_used, remaining, total_tokens, total_cost_usd } = usage
  const isPro = tier === 'pro'
  const pctUsed = limit > 0 ? Math.min(100, Math.round((jobs_used / limit) * 100)) : 0
  const isDanger = pctUsed >= 90
  const isWarning = pctUsed >= 70 && !isDanger

  return (
    <div className="panel billing-container">
      <div className="billing-card-header">
        <h2 className="panel-title" style={{ margin: 0 }}>
          Billing & Pemakaian Kuota
        </h2>
        <span className={`tier-badge ${tier}`}>{tier} Tier</span>
      </div>

      {alertMsg && (
        <div className={`billing-alert ${alertMsg.type}`}>
          {alertMsg.text}
        </div>
      )}

      <div className="billing-grid">
        <div className="billing-card">
          <div className="billing-card-header">
            <span className="billing-card-title">Kuota Generate Dokumen</span>
          </div>
          <div className="metric-value">
            {jobs_used} <span style={{ fontSize: '1rem', fontWeight: 400, color: '#8b949e' }}>/ {limit > 0 ? limit : '∞'}</span>
          </div>
          <div className="metric-sub">
            {limit > 0 ? `Sisa kuota: ${remaining} dokumen (30 hari)` : 'Kuota unlimited aktif'}
          </div>
          {limit > 0 && (
            <div className="quota-bar-container">
              <div
                className={`quota-bar-fill ${isDanger ? 'danger' : isWarning ? 'warning' : ''}`}
                style={{ width: `${pctUsed}%` }}
              />
            </div>
          )}
        </div>

        <div className="billing-card">
          <div className="billing-card-header">
            <span className="billing-card-title">Penggunaan LLM Token</span>
          </div>
          <div className="metric-value">{total_tokens.toLocaleString()}</div>
          <div className="metric-sub">Total token (Input & Output) 30 hari terakhir</div>
        </div>

        <div className="billing-card">
          <div className="billing-card-header">
            <span className="billing-card-title">Estimasi Biaya LLM</span>
          </div>
          <div className="metric-value">${total_cost_usd.toFixed(3)}</div>
          <div className="metric-sub">Berdasarkan tarif Claude Sonnet 5</div>
        </div>
      </div>

      {!isPro && (
        <div className="upgrade-banner">
          <div className="upgrade-info">
            <h3>Upgrade ke Paket Pro</h3>
            <p>
              Dapatkan kuota hingga 100 generate dokumen per bulan, pemrosesan prioritas,
              dan dukungan template kustom multi-sumber.
            </p>
          </div>
          <button
            onClick={handleUpgrade}
            disabled={checkoutLoading}
            className="btn-upgrade"
          >
            {checkoutLoading ? 'Memproses...' : 'Upgrade ke Pro ($ Stripe)'}
          </button>
        </div>
      )}
    </div>
  )
}
