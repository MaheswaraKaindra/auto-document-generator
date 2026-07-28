// "Dokumen Saya" — riwayat dokumen milik pengguna yang sedang login.
//
// Data datang dari GET /documents/jobs yang SUDAH owner-scoped di backend, jadi
// panel ini tak perlu menyaring apa pun — cukup menampilkan. Memuat ulang saat
// `reloadSignal` berubah (App menaikkannya tiap dokumen baru selesai).
import { useCallback, useEffect, useState } from 'react'
import { API_BASE_URL } from './api'
import { authHeader } from './supabaseClient'

const DOC_LABEL = { SDD: 'Solution Design', UAT: 'User Acceptance Test' }
const STATUS_LABEL = {
  queued: 'Diantrikan',
  running: 'Diproses',
  done: 'Selesai',
  failed: 'Gagal',
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('id-ID', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function DocumentsPanel({ reloadSignal }) {
  const [jobs, setJobs] = useState([])
  const [state, setState] = useState('loading') // loading | ready | error
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE_URL}/documents/jobs`, { headers: authHeader() })
      if (!resp.ok) throw new Error(String(resp.status))
      const body = await resp.json()
      setJobs(body.jobs || [])
      setState('ready')
    } catch {
      setState('error')
    }
  }, [])

  useEffect(() => {
    load()
  }, [load, reloadSignal])

  // Unduh lewat fetch+blob (bukan <a href> polos): endpoint download butuh header
  // Authorization saat auth aktif, dan href biasa tak mengirimnya. Pola sama
  // dengan unduhan utama di App.
  const download = async (job, url, suffix) => {
    setBusyId(job.job_id + suffix)
    try {
      const resp = await fetch(`${API_BASE_URL}${url}`, { headers: authHeader() })
      if (!resp.ok) throw new Error(String(resp.status))
      const blob = await resp.blob()
      const objectUrl = URL.createObjectURL(blob)
      const nama = (job.project_name || 'dokumen').replace(/[^\w.-]+/g, '_')
      const link = document.createElement('a')
      link.href = objectUrl
      link.download = suffix === '-zip'
        ? `${nama}_${job.document_type}_diagrams.zip`
        : `${nama}_${job.document_type}.docx`
      link.click()
      URL.revokeObjectURL(objectUrl)
    } catch {
      // Diamkan: tombol kembali aktif, pengguna bisa coba lagi. Kegagalan unduh
      // satu file tak perlu meruntuhkan seluruh panel.
    } finally {
      setBusyId(null)
    }
  }

  if (state === 'loading') {
    return (
      <section className="panel history">
        <h2 className="panel-title">Dokumen Saya</h2>
        <p className="hint">Memuat riwayat…</p>
      </section>
    )
  }

  if (state === 'error') {
    return (
      <section className="panel history">
        <h2 className="panel-title">Dokumen Saya</h2>
        <p className="hint">Gagal memuat riwayat. <button type="button" className="linklike" onClick={load}>Coba lagi</button></p>
      </section>
    )
  }

  return (
    <section className="panel history">
      <h2 className="panel-title">Dokumen Saya</h2>
      {jobs.length === 0 ? (
        <p className="hint">
          Belum ada dokumen. Dokumen yang Anda generate akan muncul di sini — bisa
          diunduh ulang kapan saja.
        </p>
      ) : (
        <ul className="doc-list">
          {jobs.map((job) => (
            <li className="doc-card" key={job.job_id}>
              <div className="doc-main">
                <span className="doc-name">{job.project_name || 'Tanpa nama'}</span>
                <span className="doc-meta">
                  {DOC_LABEL[job.document_type] || job.document_type}
                  {job.template_id ? ` · ${job.template_id}` : ''} · {formatDate(job.created_at)}
                </span>
              </div>
              <span className={`doc-status doc-status-${job.status}`}>
                {STATUS_LABEL[job.status] || job.status}
              </span>
              <div className="doc-actions">
                {job.download_url && (
                  <button
                    type="button"
                    onClick={() => download(job, job.download_url, '')}
                    disabled={busyId === job.job_id}
                  >
                    {busyId === job.job_id ? 'Mengunduh…' : 'Unduh .docx'}
                  </button>
                )}
                {job.diagrams_url && (
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => download(job, job.diagrams_url, '-zip')}
                    disabled={busyId === job.job_id + '-zip'}
                  >
                    {busyId === job.job_id + '-zip' ? '…' : '.drawio'}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
