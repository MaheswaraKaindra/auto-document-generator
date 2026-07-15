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
    setStatus('Memproses... (bisa beberapa saat, sistem sedang membaca repo & memanggil AI)')

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

      const blob = await response.blob()
      const filename = extractFilename(response, 'dokumen.docx')
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
      <p className="subtitle">Kerangka dasar — belum final, silakan dikembangkan lebih lanjut.</p>

      <form onSubmit={handleSubmit}>
        <label>
          Nama Project
          <input
            type="text"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="Contoh: Sistem Inventaris SPBU"
          />
        </label>

        <label>
          Tipe Dokumen
          <select value={documentType} onChange={(e) => setDocumentType(e.target.value)}>
            <option value="SDD">Solution Design Document (SDD)</option>
            <option value="UAT">User Acceptance Test (UAT)</option>
          </select>
        </label>

        <label>
          GitHub Token (Personal Access Token)
          <input
            type="password"
            value={githubToken}
            onChange={(e) => setGithubToken(e.target.value)}
            placeholder="ghp_xxxxxxxxxxxx"
          />
        </label>

        <fieldset>
          <legend>Repositori</legend>

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
          <p className="metadata-hint">
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
