import { useState } from 'react'
import './App.css'

const API_BASE_URL = 'http://localhost:8000'

const emptyRepo = () => ({ repo_tag: '', repo_url: '', branch: '' })

function extractFilename(response, fallback) {
  const disposition = response.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  return match ? match[1] : fallback
}

function App() {
  const [projectName, setProjectName] = useState('')
  const [documentType, setDocumentType] = useState('SDD')
  const [githubToken, setGithubToken] = useState('')
  const [repositories, setRepositories] = useState([emptyRepo()])
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

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Memproses...' : 'Generate Dokumen'}
        </button>
      </form>

      <p role="status">{status}</p>
    </main>
  )
}

export default App
