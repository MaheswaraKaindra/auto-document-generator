# Frontend — Kerangka Dasar (React + Vite, JavaScript)

Ini **kerangka minimal**, bukan implementasi final. Dibangun pakai React (JS, bukan
TypeScript) + Vite sesuai arahan tim. Satu halaman (`src/App.jsx`), tanpa
routing/state management library — cukup `useState` bawaan React, karena
scope-nya masih sebatas satu form.

## Cara jalankan

1. Jalankan backend FastAPI dulu (dari folder `auto-document-generator/`):
   ```
   uvicorn app.main:app --reload
   ```
2. Di folder `frontend/`, install dependency (sekali saja):
   ```
   npm install
   ```
3. Jalankan dev server:
   ```
   npm run dev
   ```
   lalu buka URL yang ditampilkan (biasanya `http://localhost:5173`).

Build untuk production: `npm run build` (hasil di folder `dist/`, tidak ikut
ter-commit — sudah ada di `.gitignore`).

## Struktur

- `src/App.jsx` — satu-satunya komponen: form input repo + token + tipe
  dokumen, submit ke backend, auto-download hasil `.docx`.
- `src/App.css`, `src/index.css` — styling dasar (support light/dark lewat
  `prefers-color-scheme`, dari template Vite bawaan, saya pertahankan).

## Kontrak API yang dipakai

Body request ke `POST /documents/generate` (lihat
`app/api/schemas_document.py` di backend), dikirim sebagai JSON:

```json
{
  "project_name": "string | null",
  "document_type": "SDD | UAT",
  "github_token": "string | null",
  "repositories": [
    { "repo_tag": "Backend", "repo_url": "https://github.com/org/repo", "branch": null }
  ]
}
```

Response: file `.docx` (binary), bukan JSON — makanya di `App.jsx` responsnya
diambil sebagai `blob`, bukan `.json()`.

`API_BASE_URL` di `App.jsx` masih hardcode ke `http://localhost:8000` — pindahkan
ke env var Vite (`import.meta.env.VITE_API_BASE_URL`) kalau nanti perlu deploy ke
environment lain.

## Belum dikerjakan / catatan

- Belum ada validasi input di luar `required` HTML bawaan.
- Belum ada indikator progress yang lebih baik dari teks status sederhana —
  proses generate bisa memakan waktu cukup lama (ingest repo + panggilan LLM).
- Sudah dites `npm run build` (berhasil, tanpa error) dan `npm install`, tapi
  **belum dites jalan sungguhan** manggil backend asli (backend juga belum
  di-smoke-test end-to-end — lihat `PERAN3_NOTES.md`).
