import { useState } from 'react'
import './App.css'

const API_BASE_URL = 'http://localhost:8000'

const emptyRepo = () => ({ repo_tag: '', repo_url: '', branch: '' })

// Field metadata dokumen: hal yang manusianya tahu tapi kode tidak akan pernah
// tahu (nomor RFC, demografi, remark security). Ditulis sebagai data, bukan JSX
// berulang, supaya menambah field cuma menambah satu baris di sini.
//
// SEMUA OPSIONAL. Yang dikosongkan jatuh balik ke penanda *(diisi manual)* di
// dokumen -- persis perilaku sebelum form ini ada. Jadi form ini boleh dilewati
// sepenuhnya, dan produk ini tetap berguna untuk repo yang memang tidak punya
// konteks enterprise (mis. proyek open-source tanpa nomor RFC).
const SDD_FIELD_GROUPS = [
  {
    legend: 'Identitas Dokumen',
    fields: [
      { key: 'solution_design_no', label: 'No. Solution Design', placeholder: 'Contoh: SD-2026-014' },
      { key: 'rfc_number', label: 'RFC #', placeholder: 'Contoh: RFC-2026-088' },
      { key: 'version', label: 'Versi', placeholder: 'Contoh: 1.0' },
      {
        key: 'document_classification',
        label: 'Document Classification',
        placeholder: 'Contoh: Internal',
      },
      // Satu-satunya dropdown: template-nya sendiri yang menyatakan pilihannya
      // ("ERP / NON ERP"). Field lain sengaja teks bebas -- mengarang enum yang
      // tidak ada di template justru memaksa pengguna ikut istilah kita.
      {
        key: 'dev_system_type',
        label: 'Application Dev System Type',
        options: ['ERP', 'NON ERP'],
      },
    ],
  },
  {
    legend: 'Informasi Demografi Aplikasi',
    fields: [
      { key: 'business_requestor', label: 'Business Requestor', placeholder: 'Divisi yang meminta' },
      { key: 'business_user', label: 'Business User', placeholder: 'Siapa yang memakai sehari-hari' },
      { key: 'projected_user_number', label: 'Projected User Number', placeholder: 'Contoh: 120 pengguna' },
      { key: 'value_rp', label: 'Value (Rp)', placeholder: 'Contoh: Rp 450.000.000' },
      { key: 'coverage_area', label: 'Application Coverage Area', placeholder: 'Contoh: Nasional' },
      { key: 'collaboration_profile', label: 'Collaboration Profile', placeholder: 'Contoh: Internal + vendor' },
      { key: 'technology_capability', label: 'Technology Capability', placeholder: 'Contoh: Web + mobile' },
    ],
  },
  {
    legend: 'Akses & Infrastruktur',
    fields: [
      { key: 'how_to_access', label: 'How to Access', multiline: true, placeholder: 'URL, jaringan, atau cara login' },
      {
        key: 'infrastructure_capacity',
        label: 'Infrastructure & Capacity Planning',
        multiline: true,
        placeholder: 'Contoh: 3 VM, 8 vCPU, 16 GB RAM',
      },
    ],
  },
  {
    legend: 'Checklist Application Security',
    fields: [
      { key: 'security_penetration_test', label: 'Penetration Test', placeholder: 'Contoh: Sudah, 2026-06-30' },
      { key: 'security_secure_coding', label: 'Secure Coding Practice', placeholder: 'Contoh: Mengikuti OWASP ASVS L2' },
      { key: 'security_reverse_proxy', label: 'Reverse Proxy', placeholder: 'Contoh: Nginx' },
    ],
  },
]

const UAT_FIELD_GROUPS = [
  {
    legend: 'Identitas Dokumen',
    fields: [
      { key: 'related_rfc_number', label: 'Related RFC #', placeholder: 'Contoh: RFC-2026-088' },
      { key: 'related_work_order', label: 'Related Work Order #', placeholder: 'Contoh: WO-2026-451' },
      { key: 'change_owner', label: 'Change Owner', placeholder: 'Penanggung jawab perubahan' },
    ],
  },
  {
    legend: 'Penyusunan & Review',
    fields: [
      { key: 'prepared_by', label: 'Prepared By', placeholder: 'Nama penyusun dokumen' },
      { key: 'preparation_date', label: 'Preparation Date', type: 'date' },
      { key: 'reviewed_by', label: 'Reviewed By', placeholder: 'Nama reviewer' },
      { key: 'review_date', label: 'Review Date', type: 'date' },
    ],
  },
  {
    legend: 'Distribusi',
    fields: [
      {
        key: 'distribution_list',
        label: 'Distribution List',
        multiline: true,
        placeholder: 'Siapa saja yang menerima dokumen ini',
      },
    ],
  },
]

const fieldGroupsFor = (documentType) =>
  documentType === 'UAT' ? UAT_FIELD_GROUPS : SDD_FIELD_GROUPS

function extractFilename(response, fallback) {
  const disposition = response.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  return match ? match[1] : fallback
}

const POLL_INTERVAL_MS = 2000
// Generation terukur ~100-190 detik pada repo nyata. 10 menit memberi ruang
// untuk repo yang jauh lebih besar tanpa menggantung tab selamanya kalau
// server-nya mati diam-diam.
const POLL_TIMEOUT_MS = 10 * 60 * 1000

/** Tanya status job sampai selesai.
 *
 *  Ada karena backend tidak lagi mengembalikan .docx di response POST: kerjanya
 *  jalan di latar belakang supaya tidak ada request yang digantung 3 menit dan
 *  diputus proxy. Konsekuensinya klien yang harus bertanya.
 */
async function pollJob(jobId, onTick) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < POLL_TIMEOUT_MS) {
    const response = await fetch(`${API_BASE_URL}/documents/jobs/${jobId}`)
    if (!response.ok) {
      throw new Error(`Gagal menanyakan status job (${response.status})`)
    }
    const job = await response.json()
    if (job.status === 'done' || job.status === 'failed') return job

    onTick(Math.round((Date.now() - startedAt) / 1000))
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
  }
  throw new Error(
    'Job belum selesai setelah 10 menit. Prosesnya mungkin masih jalan di server — ' +
      `cek /documents/jobs/${jobId} secara manual.`,
  )
}

/** Buang field kosong; kembalikan null kalau tidak ada yang diisi sama sekali,
 *  supaya request-nya jujur menyatakan "tidak ada metadata" ketimbang mengirim
 *  25 field null. */
function buildMetadataPayload(metadata, documentType) {
  const relevantKeys = fieldGroupsFor(documentType).flatMap((group) =>
    group.fields.map((field) => field.key),
  )
  const filled = Object.fromEntries(
    relevantKeys
      .map((key) => [key, (metadata[key] || '').trim()])
      .filter(([, value]) => value !== ''),
  )
  return Object.keys(filled).length > 0 ? filled : null
}

function App() {
  const [projectName, setProjectName] = useState('')
  const [documentType, setDocumentType] = useState('SDD')
  const [githubToken, setGithubToken] = useState('')
  const [repositories, setRepositories] = useState([emptyRepo()])
  const [metadata, setMetadata] = useState({})
  const [status, setStatus] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const updateRepo = (index, field, value) => {
    setRepositories((prev) =>
      prev.map((repo, i) => (i === index ? { ...repo, [field]: value } : repo)),
    )
  }

  const addRepo = () => setRepositories((prev) => [...prev, emptyRepo()])

  const removeRepo = (index) =>
    setRepositories((prev) => prev.filter((_, i) => i !== index))

  const updateMetadata = (key, value) =>
    setMetadata((prev) => ({ ...prev, [key]: value }))

  const handleSubmit = async (event) => {
    event.preventDefault()
    setIsSubmitting(true)
    setStatus('Mengirim permintaan...')

    const payload = {
      project_name: projectName || null,
      document_type: documentType,
      github_token: githubToken || null,
      repositories: repositories.map((repo) => ({
        repo_tag: repo.repo_tag,
        repo_url: repo.repo_url,
        branch: repo.branch || null,
      })),
      document_metadata: buildMetadataPayload(metadata, documentType),
    }

    try {
      const response = await fetch(`${API_BASE_URL}/documents/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        const detail = await response.text()
        throw new Error(`Server merespons ${response.status}: ${detail}`)
      }

      // 202 Accepted: pekerjaannya BELUM jalan, baru diantrikan.
      const { job_id: jobId } = await response.json()
      setStatus('Diantrikan. Sistem sedang membaca repo & memanggil AI...')

      const job = await pollJob(jobId, (seconds) =>
        setStatus(`Sedang diproses... (${seconds} detik) — biasanya 2-3 menit.`),
      )
      if (job.status === 'failed') {
        // Pesan dari server diteruskan apa adanya: dia sudah menjelaskan sebab
        // aslinya (repo kebesaran, diagram gagal, dst) dan cuma menyarankan
        // "coba lagi" kalau mengulang memang masuk akal.
        throw new Error(job.error)
      }

      setStatus('Dokumen siap, mengunduh...')
      const download = await fetch(`${API_BASE_URL}${job.download_url}`)
      if (!download.ok) {
        throw new Error(`Gagal mengunduh dokumen (${download.status})`)
      }

      const blob = await download.blob()
      const filename = extractFilename(download, 'dokumen.docx')
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      link.click()
      URL.revokeObjectURL(url)

      setStatus('Dokumen berhasil dibuat dan diunduh.')
    } catch (error) {
      setStatus(`Gagal: ${error.message}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  const renderField = (field) => (
    <label key={field.key}>
      {field.label}
      {field.options ? (
        <select
          value={metadata[field.key] || ''}
          onChange={(e) => updateMetadata(field.key, e.target.value)}
        >
          <option value="">— belum ditentukan —</option>
          {field.options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      ) : field.multiline ? (
        <textarea
          rows={2}
          value={metadata[field.key] || ''}
          onChange={(e) => updateMetadata(field.key, e.target.value)}
          placeholder={field.placeholder}
        />
      ) : (
        <input
          type={field.type || 'text'}
          value={metadata[field.key] || ''}
          onChange={(e) => updateMetadata(field.key, e.target.value)}
          placeholder={field.placeholder}
        />
      )}
    </label>
  )

  return (
    <main>
      <h1>Auto Document Generator</h1>
      <p className="subtitle">
        Tunjuk ke repo GitHub, dan sistem membaca source code-nya lalu menyusun draf dokumen{' '}
        <strong>.docx</strong> — deskripsi aplikasi, daftar fitur, use case, diagram, dan test
        case. Sekitar 2-3 menit. Hasilnya draf untuk diedit, bukan dokumen final.
      </p>

      <form onSubmit={handleSubmit}>
        <div className="field">
          <label>
            Nama Project
            <input
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="Contoh: Sistem Inventaris SPBU"
            />
          </label>
          <p className="hint">
            Muncul di halaman judul dokumen. Kalau dikosongkan, dokumennya tertulis
            “generated-project”.
          </p>
        </div>

        <div className="field">
          <label>
            Tipe Dokumen
            <select value={documentType} onChange={(e) => setDocumentType(e.target.value)}>
              <option value="SDD">Solution Design Document (SDD)</option>
              <option value="UAT">User Acceptance Test (UAT)</option>
            </select>
          </label>
          <p className="hint">
            {documentType === 'SDD' ? (
              <>
                <strong>SDD</strong> menjelaskan aplikasinya <em>seperti apa</em>: fitur, use case
                per aktor, arsitektur, dan activity diagram. Dibaca developer, product owner, dan
                reviewer.
              </>
            ) : (
              <>
                <strong>UAT</strong> berisi <em>langkah pengujiannya</em>: siapa menguji apa,
                dengan langkah dan hasil yang diharapkan. Dibaca QA dan user bisnis saat serah
                terima.
              </>
            )}{' '}
            Keduanya dibaca dari repo yang sama — pilih salah satu, jalankan lagi untuk yang lain.
          </p>
        </div>

        <div className="field">
          <label>
            GitHub Token (Personal Access Token)
            <input
              type="password"
              value={githubToken}
              onChange={(e) => setGithubToken(e.target.value)}
              placeholder="ghp_xxxxxxxxxxxx (kosongkan untuk repo publik)"
            />
          </label>
          <p className="hint">
            Perlu hanya untuk <strong>repo privat</strong>; repo publik jalan tanpa token. Token
            dipakai sekali untuk mengunduh repo — tidak ikut disimpan bersama job dan tidak
            ditulis ke log.
          </p>
        </div>

        <fieldset>
          <legend>Repositori</legend>
          <p className="hint">
            <strong>Tag</strong> menyatakan peran repo — <em>Backend</em>, <em>FE-Web</em>,{' '}
            <em>FE-CMS</em>. Bukan sekadar label: kalau frontend dan backend dimasukkan sebagai
            repo terpisah, tag inilah yang dipakai untuk memetakan pemanggilan API di frontend ke
            endpoint backend-nya, sehingga diagram integrasi komponennya benar. Satu repo saja
            juga tidak masalah.
          </p>

          {repositories.map((repo, index) => (
            <div className="repo-row" key={index}>
              <input
                type="text"
                value={repo.repo_tag}
                onChange={(e) => updateRepo(index, 'repo_tag', e.target.value)}
                placeholder="Tag (Backend / FE-Web / FE-CMS)"
                required
              />
              <input
                type="text"
                value={repo.repo_url}
                onChange={(e) => updateRepo(index, 'repo_url', e.target.value)}
                placeholder="https://github.com/org/repo"
                required
              />
              <input
                type="text"
                value={repo.branch}
                onChange={(e) => updateRepo(index, 'branch', e.target.value)}
                placeholder="Branch (opsional)"
              />
              <button
                type="button"
                className="remove-repo-btn"
                onClick={() => removeRepo(index)}
                disabled={repositories.length === 1}
                aria-label="Hapus repositori ini"
              >
                ✕
              </button>
            </div>
          ))}

          <button type="button" onClick={addRepo}>
            + Tambah Repositori
          </button>
        </fieldset>

        {/* Tertutup default: yang cuma ingin mencoba tidak dihadang tembok input,
            yang butuh dokumen siap kirim tinggal membukanya sekali. */}
        <details className="metadata-details">
          <summary>
            Informasi Dokumen <span className="optional-tag">opsional</span>
          </summary>
          <p className="hint">
            Bagian ini tidak bisa dibaca dari source code — nomor RFC, data demografi, dan
            sejenisnya cuma diketahui manusia. Yang diisi di sini langsung masuk ke dokumen;
            yang dibiarkan kosong muncul sebagai <em>(diisi manual)</em> dan bisa dilengkapi
            belakangan di Word.
          </p>

          {fieldGroupsFor(documentType).map((group) => (
            <fieldset key={group.legend}>
              <legend>{group.legend}</legend>
              {group.fields.map(renderField)}
            </fieldset>
          ))}
        </details>

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Memproses...' : 'Generate Dokumen'}
        </button>
      </form>

      <p role="status">{status}</p>
    </main>
  )
}

export default App
