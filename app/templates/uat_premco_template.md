{#
  TEMPLATE "PREMCO" untuk UAT — hasil KOMPILASI MANUAL dari docx UAT PREMCO asli
  (roadmap tahap b; pengukuran struktur & visualnya dilakukan langsung pada
  dokumennya, bukan ditebak — dokumen internal klien, di-gitignore).
  Perbedaan yang DISENGAJA terhadap uat_template.md (default), semuanya konvensi
  yang TERUKUR dari dokumen UAT aslinya:

    1. STRUKTUR FLAT TANPA HEADING. Dokumen aslinya tidak memakai style Heading
       1/2/3 sama sekali (cuma Subtitle + Normal); label bagian ditulis sebagai
       paragraf BOLD, bukan heading. Ditiru dengan **teks bold**, bukan `##`.
       Konsekuensinya premco UAT juga TANPA Daftar Isi (dokumen asli tak punya
       — _pandoc_args melewati --toc untuk kombinasi ini).
    2. Blok identitas ala UAT PREMCO: bar Related RFC, tabel Document
       Information 5-baris (RFC Name, Change Owner, Quality Review Method,
       Prepared/Reviewed By + versi/tanggal), Distribution List DUA tabel
       routing (From & To) — kerangka kosong isian manual, seperti Timeline/Cost
       di SDD premco.
    3. Case Pengujian = tabel 9 kolom ber-HEADER HIJAU (a8d08d, warna terukur
       dari dokumen asli), DIKELOMPOKKAN per modul/layar ("Case Pengujian: X").
       Marker ((GH)) pada sel pertama header dipoles post-process jadi hijau.
       Langkah pengujian multi-baris DI DALAM sel (dipisah ((BR)) — `<br/>`
       dibuang diam-diam oleh writer docx Pandoc; lihat compiler).
    4. Ringkasan Aplikasi (app_description) SENGAJA tidak dibuat bab sendiri:
       dokumen UAT asli tidak punya bab itu (isinya murni prosedur + test case).
       Aturan premco: MENGISI, bukan merestrukturisasi; slot yang tak ada di-drop.

  PENOMORAN: UAT tidak punya gambar maupun indeks, jadi tabel TIDAK diberi
  caption bernomor (dokumen aslinya juga tidak). Nomor test case restart 1..N
  per grup (loop.index), persis dokumen asli.

  CATATAN warna header: tabel boilerplate memakai header HITAM bawaan reference
  (dokumen asli putih) — beda minor yang disengaja, konsisten dengan gaya rumah
  (default & SDD premco). Yang khas UAT — header HIJAU test case — dipertahankan.
#}
**Dokumen ini merupakan rencana dan hasil pelaksanaan User Acceptance Test (UAT) untuk {{ project_name }}.**

| Related RFC # | Related Work Order # |
|--------------------|--------------------|
| {{ meta.related_rfc_number }} | {{ meta.related_work_order }} |

**Document Information**

| Keterangan | Isi | Keterangan | Isi |
|------------|--------------|----------------------|--------------|
| RFC Name | {{ project_name }} | | |
| Change Owner | {{ meta.change_owner }} | Document Version No | {{ meta.document_version_no }} |
| Quality Review Method | {{ meta.quality_review_method }} | Document Version Date | {{ meta.document_version_date }} |
| Prepared By | {{ meta.prepared_by }} | Preparation Date | {{ meta.preparation_date }} |
| Reviewed By | {{ meta.reviewed_by }} | Review Date | {{ meta.review_date }} |

**Distribution List**

| From | Date | Company / Role | Email / Phone |
|--------------|--------|--------------------|--------------------|
| | | | |

| To | Action* | Due Date | Company / Role | Email / Phone |
|--------------|--------|--------|--------------------|--------------------|
| | | | | |
| | | | | |
| | | | | |

*Action Types: Approve, Review, Inform, File, Action Required, Other (mohon dijelaskan).*

**Version History**

| Ver. No. | Ver. Date | Revised By | Description | File Name |
|--------|--------|------------|--------------------|------------|
| | | | | |

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

**Rencana Penerimaan User Acceptance Test ("UAT")**

Dokumen ini menjelaskan prosedur pelaksanaan pengujian fungsional serta metode pengujian yang digunakan dalam rangka {{ project_name }}.

Persetujuan atas dokumen ini oleh perwakilan pengguna pengujian menunjukkan bahwa hasil pengujian telah sesuai dengan kebutuhan, dan dengan demikian pengujian dianggap diterima. Nama, jabatan, dan tanda tangan perwakilan user pengujian serta perwakilan pengembang dibubuhkan pada dokumen cetak saat persetujuan diberikan.

**Perwakilan User Pengujian**

| Nama | Jabatan | Tanda Tangan |
|--------------------|--------------------|--------------------|
| | | |

**Perwakilan Pengembang**

| Nama | Jabatan | Tanda Tangan |
|--------------------|--------------------|--------------------|
| | | |

**Sertifikasi Keberhasilan Pelaksanaan Pengujian**

Tanggal penyelesaian, klasifikasi hasil (Lolos/Gagal), dan tanda tangan diisi setelah seluruh kasus pengujian pada bagian Case Pengujian selesai dieksekusi. Kerangka di bawah dilengkapi manual — hasilnya belum ada saat dokumen ini dibuat.

| No | Item | Isian |
|:---:|----------------------------------------------|--------------------|
| 1 | Tanggal Penyelesaian | |
| 2 | Klasifikasi Hasil (Lolos / Gagal) | |
| 3 | Nama & Tanda Tangan Perwakilan User Pengujian | |
| 4 | Nama & Tanda Tangan Perwakilan Pengembang | |

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

**1. Prosedur Pengujian**

**Entry Criteria**

Eksekusi pengujian hanya akan dilakukan jika kriteria-kriteria berikut sudah terpenuhi:

1. Implementasi pembuatan tampilan dan fitur {{ project_name }} telah tersaji secara penuh pada environment QAS dan dapat berfungsi dengan semestinya.

**Exit Criteria**

UAT hanya akan dianggap berhasil jika semua permasalahan yang timbul selama pelaksanaan pengujian telah diselesaikan dan ketika semua kasus pengujian, seperti yang dinyatakan dalam rencana pengujian yang telah disetujui, telah mendapat hasil yang diinginkan.

**Formulir dan Dokumentasi**

Setiap kasus pengujian yang diselesaikan oleh penguji akan didokumentasikan dengan salah satu dari status berikut.

| Status | Deskripsi |
|:------:|------------------------------|
| Lolos | Diterima apa adanya |
| Gagal | Tidak diterima dengan klarifikasi |

Semua kasus pengujian yang berstatus Gagal lebih lanjut harus dijelaskan dalam kolom Komentar, dan harus diberi kode kegagalan sebagai berikut:

| Kode Kegagalan | Deskripsi |
|:--------------:|--------------------------------------------------|
| A | Kecacatan besar atau kesalahan desain, kesalahan pada operasi software atau hardware. |
| B | Kelanjutan dari pengujian kasus tidak dapat dilakukan lagi. |
| C | Pengujian dapat terus dilakukan namun dengan beberapa keterbatasan. |
| D | Kesalahan yang menyebabkan ketidaknyamanan penggunaan oleh user tapi tidak berpengaruh langsung terhadap fungsi sistem. |

Pada saat eksekusi semua kasus pengujian telah diselesaikan, Sertifikasi Keberhasilan Pelaksanaan Pengujian harus diisi dan ditandatangani.

{# Case Pengujian di dokumen asli berada di section LANDSCAPE (diukur: section 2
   orientasi landscape, tabel test 10,9 inci lebar). Marker ini memicu section
   break + orientasi landscape di post-process (_landscape_after_marker), supaya
   9 kolom tidak berdesakan & header tidak membungkus patah-patah seperti di potret. #}
((LANDSCAPE))

{# Kolom Penguji, Tanggal Pengujian, Status, dan Komentar diisi manual oleh tim
   penguji setelah pengujian dilaksanakan — tidak bisa dihasilkan dari kode.
   Header hijau: marker ((GH)) pada sel pertama (lihat _apply_green_headers).
   Rasio dash separator = proporsi lebar kolom, diturunkan dari tabel test docx
   asli (Langkah & Hasil paling lebar) lalu disetel supaya di landscape 9-inci
   TIAP header kolom muat tanpa patah mid-kata (No:Role:Kegiatan:Langkah:Hasil:
   Penguji:Tanggal:Status:Komentar ≈ 6:12:16:36:36:13:15:10:13). #}
{% for group in uat_test_groups %}
**Case Pengujian{% if group.group_name %}: {{ group.group_name }}{% endif %}**

| ((GH))No | Role | Kegiatan | Langkah-Langkah Pengujian | Hasil yang Diharapkan | Penguji | Tanggal Pengujian | Status | Komentar |
|:------:|------------|----------------|------------------------------------|------------------------------------|-------------|---------------|----------|-------------|
{% for tc in group.test_cases -%}
| {{ loop.index }} | {{ tc.role }} | {{ tc.activity }} | {{ tc.steps }} | {{ tc.expected_result }} | | | | |
{% endfor %}

{% endfor %}
