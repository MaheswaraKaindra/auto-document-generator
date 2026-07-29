import { useState } from 'react'
import './AccountDataPanel.css'
import { API_BASE_URL } from './api'
import { authHeader } from './supabaseClient'

/**
 * Kontrol data pribadi: unduh semuanya, atau hapus semuanya (#16).
 *
 * Unduhan TIDAK memakai <a href> biasa. Endpoint-nya butuh header
 * `Authorization`, dan tag anchor tak bisa mengirim header — jadi berkasnya
 * diambil lewat fetch lalu dijadikan blob URL. Kalau ini diubah jadi anchor
 * polos, ia akan "berhasil" di mode dev (auth mati) lalu diam-diam 401 begitu
 * login dinyalakan.
 */
export default function AccountDataPanel() {
  const [busy, setBusy] = useState(null)      // 'export' | 'delete' | null
  const [pesan, setPesan] = useState(null)    // { type, text }
  const [konfirmasi, setKonfirmasi] = useState('')
  const [modeHapus, setModeHapus] = useState(false)

  const handleExport = async () => {
    setBusy('export')
    setPesan(null)
    try {
      const res = await fetch(`${API_BASE_URL}/me/export`, { headers: authHeader() })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `Gagal mengekspor data (${res.status})`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'data-saya.zip'
      a.click()
      URL.revokeObjectURL(url)
      setPesan({ type: 'success', text: 'Arsip data Anda selesai diunduh.' })
    } catch (err) {
      setPesan({ type: 'error', text: err.message })
    } finally {
      setBusy(null)
    }
  }

  const handleDelete = async () => {
    setBusy('delete')
    setPesan(null)
    try {
      const res = await fetch(`${API_BASE_URL}/me/data`, {
        method: 'DELETE',
        headers: authHeader(),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        throw new Error(body.detail || `Gagal menghapus data (${res.status})`)
      }
      // Angkanya ditampilkan, bukan disederhanakan jadi "berhasil": "0 dokumen
      // dihapus" adalah jawaban yang harus terlihat pengguna, bukan disembunyikan
      // di balik pesan sukses yang sama untuk semua kasus.
      setPesan({
        type: 'success',
        text: `Data Anda dihapus: ${body.jobs_deleted} riwayat dokumen, `
          + `${body.documents_deleted} berkas .docx, ${body.templates_deleted} template. `
          + `${body.usage_records_anonymized} catatan pemakaian diputus tautannya `
          + 'dari akun Anda.',
      })
      setModeHapus(false)
      setKonfirmasi('')
    } catch (err) {
      setPesan({ type: 'error', text: err.message })
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="panel account-data">
      <h2 className="panel-title">Data Saya</h2>
      <p className="hint">
        Kendali penuh atas data yang aplikasi ini simpan tentang akun Anda.
        Rinciannya ada di{' '}
        <a href={`${API_BASE_URL}/privacy`}>Kebijakan Privasi</a>.
      </p>

      {pesan && (
        <div className={`account-alert ${pesan.type}`}>{pesan.text}</div>
      )}

      <div className="account-actions">
        <div className="account-action">
          <div>
            <strong>Unduh semua data saya</strong>
            <p className="hint">
              Satu berkas ZIP: riwayat dokumen, berkas <code>.docx</code> yang masih
              tersimpan, template yang Anda unggah, dan catatan pemakaian.
            </p>
          </div>
          <button
            type="button"
            className="btn-secondary"
            onClick={handleExport}
            disabled={busy !== null}
          >
            {busy === 'export' ? 'Menyiapkan…' : 'Unduh ZIP'}
          </button>
        </div>

        <div className="account-action danger">
          <div>
            <strong>Hapus semua data saya</strong>
            <p className="hint">
              Riwayat, dokumen, berkas diagram, dan template Anda dihapus permanen.
              Catatan pemakaian tetap disimpan sebagai catatan biaya, tapi tautannya
              ke akun Anda diputus. <strong>Tidak bisa dibatalkan.</strong>
            </p>
          </div>
          {!modeHapus ? (
            <button
              type="button"
              className="btn-danger"
              onClick={() => { setModeHapus(true); setPesan(null) }}
              disabled={busy !== null}
            >
              Hapus data saya
            </button>
          ) : (
            <div className="konfirmasi">
              {/* Konfirmasi ketik, bukan window.confirm: satu klik tak sengaja
                  pada tombol merah tak boleh cukup untuk menghapus pekerjaan
                  berbulan-bulan. */}
              <label htmlFor="konfirmasi-hapus">
                Ketik <code>HAPUS</code> untuk memastikan:
              </label>
              <input
                id="konfirmasi-hapus"
                type="text"
                value={konfirmasi}
                onChange={(e) => setKonfirmasi(e.target.value)}
                autoComplete="off"
              />
              <div className="konfirmasi-tombol">
                <button
                  type="button"
                  className="btn-danger"
                  onClick={handleDelete}
                  disabled={konfirmasi !== 'HAPUS' || busy !== null}
                >
                  {busy === 'delete' ? 'Menghapus…' : 'Hapus permanen'}
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => { setModeHapus(false); setKonfirmasi('') }}
                  disabled={busy !== null}
                >
                  Batal
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
