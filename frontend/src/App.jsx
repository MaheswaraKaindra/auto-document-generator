import { useState, useEffect } from 'react'
import './App.css'
import { authHeader } from './supabaseClient'
import { API_BASE_URL } from './api'
import DocumentsPanel from './DocumentsPanel'

const emptyRepo = () => ({ repo_tag: '', repo_url: '', branch: '' })

// Satu repo yang di-upload sebagai ZIP. base64-nya data URL utuh
// ("data:application/zip;base64,...") — backend menoleransi & membuang prefiksnya
// sendiri, persis pola logo_base64. `error` untuk pesan per-baris (file
// kebesaran / gagal dibaca) supaya kegagalan satu ZIP tidak menjatuhkan yang lain.
const emptyZip = () => ({ repo_tag: '', filename: '', base64: '', error: '' })

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
    // Halaman cover. Dulu sel-sel ini kosong permanen di template (tidak
    // ditanyakan ke siapa pun), jadi cover selalu setengah kosong.
    legend: 'Cover — Kodifikasi & Katalog Proses Bisnis',
    fields: [
      { key: 'business_relationship_no', label: 'Business Relationship', placeholder: 'No kodifikasi' },
      { key: 'business_it_solution_no', label: 'Business IT Solution', placeholder: 'No kodifikasi' },
      { key: 'value_chain', label: 'Proses Value Chain', placeholder: 'Kategori proses bisnis' },
      { key: 'application_landscape', label: 'Application Landscape', placeholder: 'Kategori landscape aplikasi' },
    ],
  },
  {
    // Peran-perannya TETAP (diambil dari dokumen acuan); yang ditanyakan cuma
    // namanya -- nama orang tidak ada di repo mana pun.
    legend: 'Cover — Tim Project',
    fields: [
      { key: 'entitas', label: 'Entitas', placeholder: 'Nama perusahaan/organisasi (gaya premco)' },
      { key: 'team_application_requestor', label: 'Application Requestor', placeholder: 'Nama' },
      { key: 'team_business_process_owner', label: 'Business Process Owner', placeholder: 'Nama' },
      { key: 'team_pic', label: 'PIC', placeholder: 'Nama' },
      { key: 'team_lead_coordinator', label: 'Lead Coordinator', placeholder: 'Nama' },
      { key: 'team_it_solution_analyst', label: 'IT Solution Analyst', placeholder: 'Nama' },
      { key: 'team_developer', label: 'Developer', placeholder: 'Nama' },
      { key: 'team_design_uiux', label: 'Design UI/UX', placeholder: 'Nama' },
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
      { key: 'access_internal', label: 'Internal — Deskripsi', options: ['YES', 'NO'] },
      { key: 'access_internal_remark', label: 'Internal — Remark', placeholder: 'Contoh: Dapat diakses pengguna internal' },
      { key: 'access_published_internet', label: 'Published to Internet — Deskripsi', options: ['YES', 'NO'] },
      {
        key: 'access_published_internet_remark',
        label: 'Published to Internet — Remark',
        placeholder: 'Contoh: Tidak dapat diakses pengguna eksternal',
      },
      {
        key: 'infrastructure_capacity',
        label: 'Infrastructure & Capacity Planning',
        multiline: true,
        placeholder: 'Contoh: 3 VM, 8 vCPU, 16 GB RAM',
        // Gaya "premco" mengabaikan field ini: di sana bab Infrastructure adalah
        // kerangka 22 baris yang diisi manual di Word (lihat sdd_premco_template.md).
        hint: 'Dipakai gaya dokumen "Default". Gaya "PREMCO" memakai kerangka tabel yang diisi manual.',
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
// Generation terukur ~100-190 detik pada repo nyata, TAPI batas atasnya bukan
// itu: client LLM di backend diberi timeout 25 menit (llm_service.py) untuk
// repo besar. Poll timeout harus LEBIH LAMA dari itu — kalau lebih pendek,
// frontend memvonis gagal job yang sebenarnya masih jalan dan akan berhasil.
// 10 menit yang lama persis bug itu.
const POLL_TIMEOUT_MS = 30 * 60 * 1000

/** Tanya status job sampai selesai.
 *
 *  Ada karena backend tidak lagi mengembalikan .docx di response POST: kerjanya
 *  jalan di latar belakang supaya tidak ada request yang digantung 3 menit dan
 *  diputus proxy. Konsekuensinya klien yang harus bertanya.
 */
async function pollJob(jobId, onTick) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < POLL_TIMEOUT_MS) {
    const response = await fetch(`${API_BASE_URL}/documents/jobs/${jobId}`,
      { headers: authHeader() })
    if (!response.ok) {
      throw new Error(`Gagal menanyakan status job (${response.status})`)
    }
    const job = await response.json()
    if (job.status === 'done' || job.status === 'failed') return job

    // job.progress = kalimat dari server ("Membaca kode: 22 file, 38 endpoint").
    // Detiknya tetap ditampilkan terpisah: tahap AI makan ~2 menit, dan tanpa
    // angka yang bergerak, satu kalimat diam selama itu tetap terbaca hang.
    onTick(Math.round((Date.now() - startedAt) / 1000), job.progress)
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
  }
  throw new Error(
    'Job belum selesai setelah 30 menit. Prosesnya mungkin masih jalan di server — ' +
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

// Batas yang sama dengan backend (decode_logo): tolak di browser supaya
// penggunanya tahu detik itu juga, bukan setelah request bolak-balik.
const LOGO_MAX_BYTES = 2 * 1024 * 1024

// ZIP source code biasanya < 10 MB kalau node_modules/venv dikecualikan.
// base64-in-JSON membengkak ~33%, jadi batasi di 50 MB supaya tab tidak membeku
// saat encode dan body POST tidak membengkak tak wajar. Backend sendiri tak punya
// batas keras ini (cuma guard zip-bomb di ingestion) — ini pencegahan sisi klien.
const ZIP_MAX_BYTES = 50 * 1024 * 1024

// Gaya dokumen di-AMBIL dari server (GET /templates) saat mount — bukan hardcoded.
// Jadi template hasil-upload (V2) otomatis muncul, dan doc_types selalu sinkron
// dengan backend (dulu daftar statis bikin `premco` UAT ketinggalan diam-diam
// begitu backend mulai mendukungnya). Server tetap sumber kebenaran.
const BUILTIN_LABELS = {
  default: 'Bawaan (gaya acuan enterprise)',
  premco: 'Gaya PREMCO',
}
const templateLabel = (t) =>
  t.source === 'builtin' ? BUILTIN_LABELS[t.id] || t.id : t.name || t.id

// Binding "isi" (turunan-kode) — untuk meringkas hasil peta bab sesudah upload:
// berapa bab terisi otomatis dari kode. Cermin _CONTENT_BINDINGS di backend.
const CONTENT_BINDINGS = new Set([
  'app_description', 'user_roles', 'system_requirements', 'feature_requirements',
  'use_cases', 'activity_diagrams', 'architecture', 'business_flow', 'test_groups',
])

function summarizeMapping(mappings) {
  let content = 0
  for (const rows of Object.values(mappings || {})) {
    for (const m of rows) if (CONTENT_BINDINGS.has(m.binding)) content += 1
  }
  return content
}

// Label manusiawi untuk tiap binding di dropdown tinjauan. Daftar ID-nya sendiri
// datang dari server (GET /templates/{id}/bindings) supaya tak basi diam-diam;
// yang di sini cuma terjemahannya, dan ID tak dikenal jatuh ke ID mentahnya.
const BINDING_LABELS = {
  skip: '— tidak dimuat —',
  heading_only: 'Judul bab saja (anaknya yang mengisi)',
  manual: 'Placeholder (diisi manual)',
  app_description: 'Deskripsi aplikasi',
  user_roles: 'Peran pengguna',
  system_requirements: 'Kebutuhan sistem',
  feature_requirements: 'Daftar fitur',
  use_cases: 'Use case',
  activity_diagrams: 'Activity diagram',
  architecture: 'Diagram arsitektur',
  business_flow: 'Alur proses bisnis',
  test_groups: 'Tabel test case',
}
const bindingLabel = (b) => BINDING_LABELS[b] || b

function App() {
  const [projectName, setProjectName] = useState('')
  const [documentType, setDocumentType] = useState('SDD')
  // Default 'premco': instance ini premco-first, jadi tak perlu pilih tiap kali.
  const [templateId, setTemplateId] = useState('premco')
  const [githubToken, setGithubToken] = useState('')
  const [repositories, setRepositories] = useState([emptyRepo()])
  // Sumber kode: 'github' (URL) atau 'zip' (upload arsip). Backend memilih ZIP
  // kalau field zip_files terisi; kalau tidak, jatuh ke repositories GitHub.
  const [sourceType, setSourceType] = useState('github')
  const [zipRepos, setZipRepos] = useState([emptyZip()])
  const [metadata, setMetadata] = useState({})
  // { name, base64 } | null — base64-nya data URL utuh; backend menoleransi
  // (dan membuang) prefiks "data:image/...;base64," sendiri.
  const [logo, setLogo] = useState(null)
  const [logoError, setLogoError] = useState('')

  // Satu run = satu mesin status kecil, BUKAN satu string:
  //   phase   : idle | running | done | failed
  //   stages  : pesan progress dari server, berurutan — dirender sebagai log
  //             bertahap (yang lewat dicentang, yang berjalan dapat spinner).
  //             Murni dari data yang diterima, tanpa mencocokkan string, jadi
  //             mengubah tahapan di backend tidak pernah merusak tampilan ini.
  //   download: { filename, url } sesudah selesai — url-nya dipakai tombol
  //             "unduh ulang" kalau browser memblokir unduhan otomatis.
  const [phase, setPhase] = useState('idle')
  const [stages, setStages] = useState([])
  const [seconds, setSeconds] = useState(0)
  const [errorMessage, setErrorMessage] = useState('')
  const [download, setDownload] = useState(null)
  // Dinaikkan tiap dokumen selesai — memberi tahu panel "Dokumen Saya" untuk
  // memuat ulang daftarnya (tanpa mengoper fungsi/ref lintas komponen).
  const [docsReload, setDocsReload] = useState(0)

  // Gaya dokumen dari server (GET /templates) + widget upload template (V2).
  const [templates, setTemplates] = useState([])
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadUseLlm, setUploadUseLlm] = useState(false)
  const [uploadBusy, setUploadBusy] = useState(false)
  const [uploadMsg, setUploadMsg] = useState(null)   // { ok, text } | null
  const [uploadKey, setUploadKey] = useState(0)      // remount input file sesudah sukses

  // Tinjauan peta bab (V2) — langkah terakhir yang tak bisa diotomatiskan.
  // Ekstraksi menemukan babnya dan pemeta menebak isinya, tapi cuma pemberi
  // template yang tahu bab bernama asing itu sebetulnya diisi apa.
  //   review        : { manifest, mappings } dari server | null (built-in = null)
  //   reviewDocType : peta jenis dokumen mana yang sedang disunting
  //   reviewDraft   : { [docType]: string[] } — binding yang SEDANG disunting,
  //                   dipisah dari `review` supaya "belum disimpan" kelihatan.
  const [review, setReview] = useState(null)
  const [reviewDocType, setReviewDocType] = useState(null)
  const [reviewDraft, setReviewDraft] = useState({})
  const [bindingOptions, setBindingOptions] = useState([])
  const [reviewBusy, setReviewBusy] = useState(false)
  const [reviewMsg, setReviewMsg] = useState(null)   // { ok, text } | null

  const openReview = (detail) => {
    const docTypes = Object.keys(detail?.mappings || {})
    setReview(detail)
    setReviewDocType(docTypes[0] || null)
    setReviewDraft(
      Object.fromEntries(
        Object.entries(detail?.mappings || {}).map(([dt, rows]) => [
          dt,
          rows.map((r) => r.binding),
        ]),
      ),
    )
    setReviewMsg(null)
  }

  const fetchTemplates = async () => {
    try {
      const resp = await fetch(`${API_BASE_URL}/templates`, { headers: authHeader() })
      if (resp.ok) setTemplates((await resp.json()).templates || [])
    } catch {
      // gagal ambil daftar: dropdown fallback ke 'premco' (tetap valid di backend)
    }
  }
  useEffect(() => {
    fetchTemplates()
    // Pilihan isi datang dari server, bukan disalin ke sini — kalau backend
    // menambah binding baru, dropdown ini ikut tanpa perubahan frontend.
    fetch(`${API_BASE_URL}/templates/bindings`, { headers: authHeader() })
      .then((r) => (r.ok ? r.json() : null))
      .then((b) => b && setBindingOptions(b.bindings || []))
      .catch(() => {})
  }, [])

  // Peta bab cuma ada untuk template HASIL UPLOAD. Built-in ('default'/'premco')
  // sengaja tak bisa disunting: keduanya dikompilasi tangan dan sudah terverifikasi
  // ke dokumen acuan — membuka suntingannya cuma jalan merusak yang sudah benar.
  useEffect(() => {
    const chosen = templates.find((t) => t.id === templateId)
    if (!chosen || chosen.source === 'builtin') {
      setReview(null)
      return
    }
    let stale = false
    fetch(`${API_BASE_URL}/templates/${encodeURIComponent(templateId)}`,
      { headers: authHeader() })
      .then((r) => (r.ok ? r.json() : null))
      .then((detail) => {
        if (!stale && detail) openReview(detail)
      })
      .catch(() => {})
    return () => {
      stale = true
    }
  }, [templateId, templates])

  const saveReview = async () => {
    if (!review || !reviewDocType) return
    setReviewBusy(true)
    setReviewMsg(null)
    try {
      const templateId_ = review.manifest.template_id
      const resp = await fetch(
        `${API_BASE_URL}/templates/${encodeURIComponent(templateId_)}/mappings/${reviewDocType}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', ...authHeader() },
          body: JSON.stringify({ bindings: reviewDraft[reviewDocType] || [] }),
        },
      )
      const body = await resp.json().catch(() => ({}))
      if (!resp.ok) throw new Error(body.detail || `Gagal menyimpan peta (${resp.status})`)
      openReview(body)
      setReviewMsg({ ok: true, text: 'Peta bab tersimpan — template diperbarui.' })
    } catch (e) {
      setReviewMsg({ ok: false, text: e.message })
    } finally {
      setReviewBusy(false)
    }
  }

  const pushStage = (message) =>
    setStages((prev) => (prev[prev.length - 1] === message ? prev : [...prev, message]))

  const updateRepo = (index, field, value) => {
    setRepositories((prev) =>
      prev.map((repo, i) => (i === index ? { ...repo, [field]: value } : repo)),
    )
  }

  const addRepo = () => setRepositories((prev) => [...prev, emptyRepo()])

  const removeRepo = (index) =>
    setRepositories((prev) => prev.filter((_, i) => i !== index))

  const updateZip = (index, patch) =>
    setZipRepos((prev) => prev.map((zip, i) => (i === index ? { ...zip, ...patch } : zip)))

  const addZip = () => setZipRepos((prev) => [...prev, emptyZip()])

  const removeZip = (index) =>
    setZipRepos((prev) => prev.filter((_, i) => i !== index))

  // File .zip -> base64 (data URL) via FileReader, pola sama dengan logo. File
  // kebesaran/gagal-baca disimpan sebagai error per-baris, bukan dilempar.
  const handleZipFile = (index, event) => {
    const file = event.target.files?.[0]
    if (!file) {
      updateZip(index, { filename: '', base64: '', error: '' })
      return
    }
    if (file.size > ZIP_MAX_BYTES) {
      event.target.value = ''
      updateZip(index, {
        filename: '',
        base64: '',
        error:
          `File ${(file.size / 1024 / 1024).toFixed(1)} MB — maksimum 50 MB. ` +
          'Kecualikan node_modules, venv, dan folder build dari ZIP; itu tidak dibaca dan cuma memperbesar unggahan.',
      })
      return
    }
    const reader = new FileReader()
    reader.onload = () => updateZip(index, { filename: file.name, base64: reader.result, error: '' })
    reader.onerror = () =>
      updateZip(index, { filename: '', base64: '', error: 'Gagal membaca file ZIP — coba pilih ulang.' })
    reader.readAsDataURL(file)
  }

  const updateMetadata = (key, value) =>
    setMetadata((prev) => ({ ...prev, [key]: value }))

  const handleLogoChange = (event) => {
    const file = event.target.files?.[0]
    setLogoError('')
    if (!file) {
      setLogo(null)
      return
    }
    if (file.size > LOGO_MAX_BYTES) {
      setLogo(null)
      event.target.value = ''
      setLogoError(
        `File ${(file.size / 1024 / 1024).toFixed(1)} MB — maksimum 2 MB. ` +
          'Logo header tidak butuh resolusi besar; ekspor versi kecilnya.',
      )
      return
    }
    const reader = new FileReader()
    reader.onload = () => setLogo({ name: file.name, base64: reader.result })
    reader.onerror = () => setLogoError('Gagal membaca file logo — coba pilih ulang.')
    reader.readAsDataURL(file)
  }

  const handleUploadTemplate = async () => {
    if (!uploadFile) return
    setUploadBusy(true)
    setUploadMsg(null)
    try {
      const form = new FormData()
      form.append('file', uploadFile)
      if (uploadUseLlm) form.append('use_llm_mapping', 'true')
      const resp = await fetch(`${API_BASE_URL}/templates`,
        { method: 'POST', body: form, headers: authHeader() })
      const body = await resp.json().catch(() => ({}))
      if (!resp.ok) throw new Error(body.detail || `Gagal upload template (${resp.status})`)

      const tid = body.manifest.template_id
      const tDocTypes = Object.keys(body.manifest.doc_types || {})
      const content = summarizeMapping(body.mappings)

      await fetchTemplates()
      setTemplateId(tid)
      // kalau template baru tak mendukung jenis dokumen yang sedang dipilih,
      // ikut pindah supaya kombinasi tetap valid (tak kena 422 saat generate).
      if (tDocTypes.length && !tDocTypes.includes(documentType)) {
        setDocumentType(tDocTypes[0])
      }
      setUploadFile(null)
      setUploadUseLlm(false)
      setUploadKey((k) => k + 1)
      setUploadMsg({
        ok: true,
        text:
          content > 0
            ? `Template "${body.manifest.name || tid}" terdaftar & dipilih — ${content} bab terisi otomatis dari kode.`
            : `Template "${body.manifest.name || tid}" terdaftar & dipilih, tapi belum ada bab yang bisa diisi dari kode. Untuk template dengan nama bab tak umum, centang "pemetaan AI" lalu upload ulang.`,
      })
    } catch (e) {
      setUploadMsg({ ok: false, text: e.message })
    } finally {
      setUploadBusy(false)
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()

    // Sumber kode dipilih di section 2. Kalau ZIP, kumpulkan hanya baris yang
    // file-nya sudah terbaca DAN punya tag, lalu tolak lebih awal (dengan pesan
    // jelas) daripada mengirim request yang pasti gagal di server.
    const usingZip = sourceType === 'zip'
    const zipFiles = zipRepos
      .filter((zip) => zip.base64 && zip.repo_tag.trim())
      .map((zip) => ({ repo_tag: zip.repo_tag.trim(), filename: zip.filename, zip_base64: zip.base64 }))
    if (usingZip && zipFiles.length === 0) {
      setPhase('failed')
      setErrorMessage('Pilih minimal satu file ZIP beserta Tag-nya sebelum generate.')
      return
    }

    setPhase('running')
    setStages(['Mengirim permintaan ke server…'])
    setSeconds(0)
    setErrorMessage('')
    setDownload(null)

    const payload = {
      project_name: projectName || null,
      document_type: documentType,
      // ZIP dan GitHub saling menggantikan: kirim salah satu, kosongkan yang lain
      // supaya backend memilih jalur yang benar (zip_files menang kalau terisi).
      github_token: usingZip ? null : githubToken || null,
      repositories: usingZip
        ? []
        : repositories.map((repo) => ({
            repo_tag: repo.repo_tag,
            repo_url: repo.repo_url,
            branch: repo.branch || null,
          })),
      zip_files: usingZip ? zipFiles : null,
      document_metadata: buildMetadataPayload(metadata, documentType),
      logo_base64: logo?.base64 || null,
      template_id: templateId,
    }

    try {
      const response = await fetch(`${API_BASE_URL}/documents/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        const detail = await response.text()
        throw new Error(`Server merespons ${response.status}: ${detail}`)
      }

      // 202 Accepted: pekerjaannya BELUM jalan, baru diantrikan.
      const { job_id: jobId } = await response.json()
      pushStage('Diantrikan — menunggu giliran…')

      const job = await pollJob(jobId, (elapsed, progress) => {
        setSeconds(elapsed)
        if (progress) pushStage(progress)
      })
      if (job.status === 'failed') {
        // Pesan dari server diteruskan apa adanya: dia sudah menjelaskan sebab
        // aslinya (repo kebesaran, token kurang, dst) dan cuma menyarankan
        // "coba lagi" kalau mengulang memang masuk akal.
        throw new Error(job.error)
      }

      pushStage('Dokumen siap — mengunduh…')
      const downloadUrl = `${API_BASE_URL}${job.download_url}`
      const fileResponse = await fetch(downloadUrl, { headers: authHeader() })
      if (!fileResponse.ok) {
        throw new Error(`Gagal mengunduh dokumen (${fileResponse.status})`)
      }

      const blob = await fileResponse.blob()
      const filename = extractFilename(fileResponse, 'dokumen.docx')
      const objectUrl = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = objectUrl
      link.download = filename
      link.click()
      URL.revokeObjectURL(objectUrl)

      setDownload({ filename, url: downloadUrl })
      setPhase('done')
      setDocsReload((n) => n + 1)   // dokumen baru -> segarkan "Dokumen Saya"
    } catch (error) {
      setErrorMessage(error.message)
      setPhase('failed')
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
      {field.hint && <p className="hint">{field.hint}</p>}
    </label>
  )

  const isSubmitting = phase === 'running'
  // Gaya dokumen yang cocok untuk jenis dokumen terpilih (server yang menentukan).
  const availableTemplates = templates.filter((t) => t.doc_types.includes(documentType))

  return (
    <main>
      <header className="masthead">
        <p className="kicker">Solution Design · User Acceptance Test</p>
        <h1>Auto Document Generator</h1>
        <p className="subtitle">
          Tunjuk ke repo GitHub atau upload ZIP source code-nya, dan sistem membacanya lalu menyusun draf dokumen{' '}
          <strong>.docx</strong> — deskripsi aplikasi, daftar fitur, use case, diagram, dan test
          case. Sekitar 2-3 menit. Hasilnya draf untuk diedit, bukan dokumen final.
        </p>
      </header>

      <form onSubmit={handleSubmit}>
        <section className="panel">
          <h2 className="panel-title">
            <span className="panel-num">1</span> Dokumen
          </h2>

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
              Ini <strong>nama aplikasinya di seluruh dokumen</strong>, bukan cuma judul —
              AI memakainya saat menulis deskripsi dan use case, karena nama asli aplikasi
              tidak selalu bisa ditebak dari kodenya. Tulis nama yang Anda ingin dibaca
              orang. Kalau dikosongkan, dokumennya tertulis “generated-project”.
            </p>
          </div>

          <div className="field">
            <label>
              Tipe Dokumen
              <select
                value={documentType}
                onChange={(e) => {
                  const nextType = e.target.value
                  setDocumentType(nextType)
                  const chosen = templates.find((t) => t.id === templateId)
                  if (chosen && !chosen.doc_types.includes(nextType)) setTemplateId('premco')
                }}
              >
                <option value="SDD">Solution Design Document (SDD)</option>
                <option value="UAT">User Acceptance Test (UAT)</option>
              </select>
            </label>
            <p className="hint">
              {documentType === 'SDD' ? (
                <>
                  <strong>SDD</strong> menjelaskan aplikasinya <em>seperti apa</em>: fitur, use
                  case per aktor, arsitektur, dan activity diagram. Dibaca developer, product
                  owner, dan reviewer.
                </>
              ) : (
                <>
                  <strong>UAT</strong> berisi <em>langkah pengujiannya</em>: siapa menguji apa,
                  dengan langkah dan hasil yang diharapkan. Dibaca QA dan user bisnis saat serah
                  terima.
                </>
              )}{' '}
              Keduanya dibaca dari repo yang sama — pilih salah satu, jalankan lagi untuk yang
              lain.
            </p>
          </div>

          <div className="field">
            <label>
              Gaya Dokumen
              <select value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
                {availableTemplates.length === 0 ? (
                  <option value="premco">memuat gaya dokumen…</option>
                ) : (
                  availableTemplates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {templateLabel(t)}
                    </option>
                  ))
                )}
              </select>
            </label>
            <p className="hint">
              Isi dokumennya sama — yang berbeda <strong>bentuk penyajiannya</strong>. Gaya
              PREMCO meniru konvensi dokumen aslinya; template <strong>hasil upload Anda</strong>{' '}
              (di bawah) muncul di sini setelah didaftarkan.
            </p>

            <div className="upload-box">
              <label>
                Upload Template Sendiri (opsional)
                <input
                  key={uploadKey}
                  type="file"
                  accept=".docx"
                  onChange={(e) => {
                    setUploadFile(e.target.files?.[0] || null)
                    setUploadMsg(null)
                  }}
                />
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={uploadUseLlm}
                  onChange={(e) => setUploadUseLlm(e.target.checked)}
                />
                Petakan bab dengan AI (berbayar) — untuk template yang nama babnya tak umum
              </label>
              <button
                type="button"
                onClick={handleUploadTemplate}
                disabled={!uploadFile || uploadBusy}
              >
                {uploadBusy ? 'Mengunggah…' : 'Upload & Daftarkan Template'}
              </button>
              {uploadMsg && (
                <p className={`upload-msg${uploadMsg.ok ? '' : ' error'}`}>{uploadMsg.text}</p>
              )}
              <p className="hint">
                File <strong>.docx</strong> template perusahaan Anda — sistem mengukur gayanya
                (font, tabel, struktur bab) lalu mendaftarkannya sebagai Gaya Dokumen baru. Bab
                yang bisa diturunkan dari kode diisi otomatis; sisanya jadi placeholder{' '}
                <em>(diisi manual)</em>. Tanpa AI, hanya bab bernama umum yang dikenali.
              </p>
            </div>

            {review && reviewDocType && (
              <div className="review-box">
                <div className="review-head">
                  <strong>Tinjau Peta Bab — {review.manifest.name || review.manifest.template_id}</strong>
                  {Object.keys(review.mappings).length > 1 && (
                    <select
                      value={reviewDocType}
                      onChange={(e) => setReviewDocType(e.target.value)}
                    >
                      {Object.keys(review.mappings).map((dt) => (
                        <option key={dt} value={dt}>
                          {dt}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                {review.manifest.mapping_health?.[reviewDocType]?.warning && (
                  <p className="review-warning">
                    {review.manifest.mapping_health[reviewDocType].warning}
                  </p>
                )}

                <ul className="review-list">
                  {review.mappings[reviewDocType].map((row, i) => (
                    <li key={`${row.text}-${i}`} style={{ paddingLeft: `${(row.level - 1) * 16}px` }}>
                      <span className="review-chapter" title={row.text}>
                        {row.text || <em>(bab tanpa judul)</em>}
                      </span>
                      <select
                        value={reviewDraft[reviewDocType]?.[i] ?? row.binding}
                        onChange={(e) =>
                          setReviewDraft((draft) => {
                            const next = [...(draft[reviewDocType] || [])]
                            next[i] = e.target.value
                            return { ...draft, [reviewDocType]: next }
                          })
                        }
                      >
                        {bindingOptions.map((b) => (
                          <option key={b} value={b}>
                            {bindingLabel(b)}
                          </option>
                        ))}
                      </select>
                    </li>
                  ))}
                </ul>

                <button type="button" onClick={saveReview} disabled={reviewBusy}>
                  {reviewBusy ? 'Menyimpan…' : 'Simpan Peta Bab'}
                </button>
                {reviewMsg && (
                  <p className={`upload-msg${reviewMsg.ok ? '' : ' error'}`}>{reviewMsg.text}</p>
                )}
                <p className="hint">
                  Sistem sudah menebak isi tiap bab dari namanya, tapi hanya Anda yang tahu
                  maksud bab di template perusahaan Anda — mis. bab yang sebetulnya tempat
                  <strong> screenshot</strong> atau <strong>tanda tangan</strong> sebaiknya
                  dibiarkan <em>Placeholder</em>. Tiap isi hanya boleh dipakai satu bab.
                </p>
              </div>
            )}
          </div>

          <div className="field">
            <label>
              Logo Perusahaan (opsional)
              <input type="file" accept="image/png,image/jpeg" onChange={handleLogoChange} />
            </label>
            {logo && (
              <div className="logo-preview">
                <img src={logo.base64} alt={`Preview ${logo.name}`} />
                <span className="hint">
                  <strong>{logo.name}</strong> akan dipasang di header — pastikan ini logo yang benar.
                </span>
                <button type="button" className="remove-repo-btn" onClick={() => setLogo(null)}>
                  ✕
                </button>
              </div>
            )}
            {logoError && <p className="hint">{logoError}</p>}
            <p className="hint">
              PNG/JPEG, maks 2 MB. Muncul di <strong>kanan atas setiap halaman</strong> dokumen —
              seperti kop dokumen resmi perusahaan. Kosongkan kalau tidak perlu; dokumennya tetap
              utuh tanpa logo.
            </p>
          </div>
        </section>

        <section className="panel">
          <h2 className="panel-title">
            <span className="panel-num">2</span> Sumber Kode
          </h2>

          <div className="field">
            <label>
              Dari mana source code-nya?
              <select value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
                <option value="github">Repo GitHub (URL)</option>
                <option value="zip">Upload file ZIP</option>
              </select>
            </label>
            <p className="hint">
              {sourceType === 'github' ? (
                <>
                  Tunjuk URL repo GitHub — <strong>publik</strong> jalan tanpa token,{' '}
                  <strong>privat</strong> perlu token di bawah.
                </>
              ) : (
                <>
                  Upload arsip <strong>.zip</strong> berisi source code — untuk repo yang tidak ada
                  di GitHub atau yang aksesnya tidak ingin Anda bagikan. Diproses lewat pipeline
                  yang sama (baca kode → AI → .docx).
                </>
              )}
            </p>
          </div>

          {sourceType === 'github' ? (
            <>
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
                  Perlu hanya untuk <strong>repo privat</strong>; repo publik jalan tanpa token.
                  Token dipakai sekali untuk mengunduh repo — tidak ikut disimpan bersama job dan
                  tidak ditulis ke log.
                </p>
              </div>

              <fieldset className="repo-group">
                <legend>Repositori</legend>
                <p className="hint">
                  <strong>Tag</strong> menyatakan peran repo — <em>Backend</em>, <em>FE-Web</em>,{' '}
                  <em>FE-CMS</em>. Bukan sekadar label: kalau frontend dan backend dimasukkan
                  sebagai repo terpisah, tag inilah yang dipakai untuk memetakan pemanggilan API di
                  frontend ke endpoint backend-nya, sehingga diagram integrasi komponennya benar.
                  Satu repo saja juga tidak masalah.
                </p>

                {repositories.map((repo, index) => (
                  <div className="repo-row" key={index}>
                    <input
                      type="text"
                      value={repo.repo_tag}
                      onChange={(e) => updateRepo(index, 'repo_tag', e.target.value)}
                      placeholder="Tag (Backend / FE-Web)"
                      aria-label="Tag peran repositori"
                      required
                    />
                    <input
                      type="text"
                      value={repo.repo_url}
                      onChange={(e) => updateRepo(index, 'repo_url', e.target.value)}
                      placeholder="https://github.com/org/repo"
                      aria-label="URL repositori GitHub"
                      required
                    />
                    <input
                      type="text"
                      value={repo.branch}
                      onChange={(e) => updateRepo(index, 'branch', e.target.value)}
                      placeholder="Branch (opsional)"
                      aria-label="Branch (opsional)"
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
            </>
          ) : (
            <fieldset className="repo-group">
              <legend>Repositori (ZIP)</legend>
              <p className="hint">
                Satu ZIP = satu repo. Seperti jalur GitHub, <strong>Tag</strong>-nya (
                <em>Backend</em>, <em>FE-Web</em>) yang dipakai memetakan pemanggilan API di
                frontend ke endpoint backend, sehingga diagram integrasinya benar. Kecualikan{' '}
                <em>node_modules</em>, <em>venv</em>, dan folder build dari ZIP — tidak dibaca dan
                cuma memperbesar unggahan.
              </p>

              {zipRepos.map((zip, index) => (
                <div key={index}>
                  <div className="zip-row">
                    <input
                      type="text"
                      value={zip.repo_tag}
                      onChange={(e) => updateZip(index, { repo_tag: e.target.value })}
                      placeholder="Tag (Backend / FE-Web)"
                      aria-label="Tag peran repositori"
                      required
                    />
                    <input
                      type="file"
                      accept=".zip,application/zip"
                      onChange={(e) => handleZipFile(index, e)}
                      aria-label="File ZIP repositori"
                      required
                    />
                    <button
                      type="button"
                      className="remove-repo-btn"
                      onClick={() => removeZip(index)}
                      disabled={zipRepos.length === 1}
                      aria-label="Hapus ZIP ini"
                    >
                      ✕
                    </button>
                  </div>
                  {zip.error ? (
                    <p className="zip-status error">{zip.error}</p>
                  ) : zip.filename ? (
                    <p className="zip-status">{zip.filename} — siap diunggah.</p>
                  ) : null}
                </div>
              ))}

              <button type="button" onClick={addZip}>
                + Tambah ZIP
              </button>
            </fieldset>
          )}
        </section>

        {/* Tertutup default: yang cuma ingin mencoba tidak dihadang tembok input,
            yang butuh dokumen siap kirim tinggal membukanya sekali. */}
        <details className="panel metadata-details">
          <summary>
            <span className="panel-title">
              <span className="panel-num">3</span> Informasi Dokumen
            </span>
            <span className="optional-tag">opsional</span>
          </summary>

          <div className="metadata-body">
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
          </div>
        </details>

        <button type="submit" className="submit-btn" disabled={isSubmitting}>
          {isSubmitting ? 'Sedang memproses…' : 'Generate Dokumen'}
        </button>
      </form>

      {stages.length > 0 && (
        <section className="run-panel" role="status" aria-live="polite">
          <ol className="stage-list">
            {stages.map((stage, index) => {
              const isLast = index === stages.length - 1
              const state = !isLast
                ? 'done'
                : phase === 'running'
                  ? 'active'
                  : phase === 'failed'
                    ? 'failed'
                    : 'done'
              return (
                <li key={index} className={`stage stage-${state}`}>
                  <span className="stage-icon" aria-hidden="true">
                    {state === 'done' ? '✓' : state === 'failed' ? '✕' : ''}
                  </span>
                  <span>{stage}</span>
                </li>
              )
            })}
          </ol>
          {phase === 'running' && (
            <p className="elapsed">{seconds} detik — biasanya selesai dalam 2-3 menit.</p>
          )}
        </section>
      )}

      {phase === 'failed' && <div className="alert alert-error">{errorMessage}</div>}

      {phase === 'done' && download && (
        <div className="alert alert-success">
          <strong>{download.filename}</strong> berhasil dibuat dan diunduh otomatis.{' '}
          <a href={download.url}>Unduh ulang</a> kalau file-nya tidak muncul di folder unduhan.
        </div>
      )}

      <DocumentsPanel reloadSignal={docsReload} />
    </main>
  )
}

export default App
