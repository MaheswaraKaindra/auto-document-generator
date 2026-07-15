# Kerangka Validasi

Menjalankan pipeline terhadap repo publik nyata yang beragam, untuk mengetahui
di mana produk ini patah di dunia yang belum pernah kita lihat.

## Ini bukan pengganti pytest

| | `pytest` | Harness ini |
|---|---|---|
| Menjawab | "apakah kode melakukan yang kita rancang?" | "apakah rancangan kita bertahan di repo asing?" |
| Mermaid & LLM | selalu di-mock | sungguhan |
| Biaya | gratis | GitHub API + (opsional) Claude berbayar |
| Waktu | ~4 detik | menit sampai puluhan menit |
| Hasil | lolos/gagal | angka + dokumen yang harus dibaca manusia |

Keduanya saling melengkapi. Buktinya bug `414` mermaid.ink: **11 test hijau
semua sementara produknya rusak untuk repo nyata**, karena mermaid.ink di-mock.
Validasi menemukan yang tak terduga; test mengunci supaya tak terulang.

## Dua tahap, dipisah berdasarkan biaya

**Tahap 1 — gratis (default).** `ingest -> parse`. Tidak menyentuh LLM. Contract A
disimpan ke `out/` supaya Tahap 2 tidak perlu ingest ulang.

**Tahap 2 — berbayar (`--with-llm`).** `Contract A -> LLM -> docx`. Satu kasus =
satu panggilan Claude. Wajib opt-in dan minta konfirmasi.

Alurnya: jalankan Tahap 1 ke semua kasus, baca laporan, lalu Tahap 2 hanya ke
2–3 kasus yang paling layak dibayari.

```bash
python scripts/validation/run_validation.py --list          # lihat daftar kasus
python scripts/validation/run_validation.py                 # Tahap 1, semua (gratis)
python scripts/validation/run_validation.py --only flask    # Tahap 1, satu kasus
python scripts/validation/run_validation.py --only flask --with-llm   # BERBAYAR
```

## `GITHUB_TOKEN` — dianjurkan, tidak lagi wajib

Sejak ingestion pindah ke tarball (2026-07-15, lihat Temuan), satu repo cuma
memakan **~2 request API** berapa pun jumlah filenya — unduhan tarball-nya lewat
codeload dan tidak memotong jatah. Jadi batas anonim 60/jam sudah cukup untuk
menjalankan seluruh daftar kasus.

Token tetap dianjurkan (batas naik jadi 5.000/jam, dan perlu untuk repo privat),
tapi bukan lagi penghalang. Harness tetap memeriksa jatah sebelum mulai dan
menolak jalan kalau tidak cukup, supaya kehabisan jatah muncul dalam sedetik
sebagai pesan jelas, bukan hang tanpa sebab.

## Membaca hasilnya

Metrik utamanya **`coverage`**: porsi file yang tipenya berhasil dikenali
(`controller`/`service`/`model`/`ui_component`) versus yang jatuh ke fallback
`"other"`.

Coverage rendah berarti LLM cuma menerima nama file tanpa struktur — dan di
situlah bahayanya: **LLM tetap akan menghasilkan dokumen yang terbaca meyakinkan**.
Dokumen yang bagus di atas coverage rendah bukan kabar baik, itu tanda karangan.
Karena itu `repos.json` sengaja memuat repo Go dan Java yang kita tahu akan jatuh
ke fallback — untuk mengukur seberapa besar lubangnya, dan untuk melihat apakah
LLM mengarang saat kekurangan bahan.

Angka tidak bisa menilai apakah dokumennya bagus. Buka `.docx`-nya dan baca —
bagian itu memang tidak bisa diotomatiskan, apalagi produk ini menjanjikan
dokumen yang dipahami pembaca non-teknis.

## Kasus yang dipilih

Tiap kasus menguji satu asumsi (`asumsi_yang_diuji` di `repos.json`), bukan asal
menumpuk repo:

| Kasus | Menguji |
|---|---|
| `flask`, `express` | Baseline bahasa yang didukung penuh |
| `realworld-fullstack` | Cross-repo mapping FE↔BE — pembeda utama produk |
| `requests-library` | Asumsi diam-diam "setiap repo adalah aplikasi web" |
| `gin-go`, `spring-petclinic-java` | Besarnya lubang bahasa yang belum didukung |
| `fastapi-large` | Skala: waktu ingest, ukuran Contract A, ukuran diagram |

## Temuan

**2026-07-15 — Ingestion 1 request per file. SUDAH DIPERBAIKI.** Ditemukan saat
percobaan pertama harness ini: mencoba `express` (repo kecil) menghabiskan
seluruh 60 request anonim lalu menggantung >7 menit tanpa sebab yang kelihatan.
Akarnya `get_git_blob()` dipanggil per file di `github_provider.py`.

Dampaknya lebih besar dari sekadar validasi — ini menyentuh produk: untuk SaaS
yang menjanjikan "repo mana pun", ingest satu repo berarti ratusan panggilan API
berurutan, lambat dan boros kuota pengguna.

Diperbaiki dengan mengunduh tarball repo dalam satu request lalu membongkarnya di
memori: biaya API turun dari ~N request (N = jumlah file) jadi ~2 per repo,
konstan berapa pun ukuran reponya. Harness juga diberi preflight cek jatah, jadi
kehabisan kuota tidak lagi muncul sebagai hang misterius.

Harness ini membuktikan nilainya justru dengan gagal pada percobaan perdananya —
itu memang gunanya.
