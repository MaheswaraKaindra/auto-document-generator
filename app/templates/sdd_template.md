{#
  PENOMORAN GAMBAR & TABEL — baca ini sebelum menambah gambar/tabel.

  Nomornya ditanam langsung di teks caption ("Gambar 5 ..."), bukan dihitung
  Word. Word cuma mengumpulkan caption itu ke Daftar Gambar/Tabel dan menambahkan
  nomor HALAMAN-nya. Jadi urutan di sini WAJIB urut dokumen, dan offset di bawah
  adalah jumlah gambar/tabel tetap yang mendahului loop-nya:

    Gambar 1-4 tetap : Arsitektur Sistem, Integrasi Komponen, Flow Proses
                       Bisnis, Use Case Diagram
    Gambar 5..N      : activity diagram      -> loop.index + 4
    Tabel  1-6 tetap : Role Pengguna, Demografi, System Requirement,
                       How to Access, Security, Features Requirement
    Tabel  7..N      : use case per aktor    -> loop.index + 6
    Tabel  N+1..     : activity diagram      -> loop.index + 6 + use_cases|length

  Menambah gambar/tabel TETAP berarti offset ikut naik — di SEMUA tempatnya.
  Kalau lupa, penomorannya bentrok tanpa error apa pun.

  Keempat gambar tetap dijamin ada: compiler mengaksesnya dengan diagrams["..."]
  (KeyError kalau hilang) dan render yang gagal melempar DiagramRenderError, jadi
  dokumen yang jadi pasti punya keempatnya — tidak ada Gambar 2 tanpa Gambar 1.

  Tabel front-matter (identitas cover, Revision History, Timeline, Cost,
  tanda tangan) sengaja TIDAK di-caption: dokumen acuan pun tidak menomorinya —
  penomoran isinya dimulai dari tabel role pengguna di Deskripsi Aplikasi.

  URUTAN HALAMAN meniru dokumen acuan: cover (judul + identitas), riwayat
  revisi, persetujuan, LALU Daftar Isi/Gambar/Tabel, baru isi. Karena Pandoc
  memaku --toc/--lof/--lot tepat sesudah judul (sebelum body), ketiga daftar
  itu ditanam DI SINI sebagai field code Word (blok {=openxml} di bawah) dan
  Word mengisinya saat dokumen dibuka (updateFields dibawa reference.docx).
  Style "TOCHeading" membawa pageBreakBefore, jadi tiap daftar otomatis mulai
  di halaman baru — tidak perlu page break manual di sekitarnya.

  LEBAR KOLOM tabel diatur RASIO DASH pada separator row (dibaca Pandoc karena
  --columns=30 di compiler): dash lebih banyak = kolom lebih lebar; `:---:` =
  kolom rata tengah. Mengubah jumlah dash mengubah proporsi kolom — itu fitur,
  bukan kebetulan.
#}
| Field | Isi |
|----------|--------------------|
| Nama Project | {{ project_name }} |
| No. Solution Design | {{ meta.solution_design_no }} |
| RFC # | {{ meta.rfc_number }} |
| Versi | {{ meta.version }} |
| Document Classification | {{ meta.document_classification }} |

{# Tiga tabel di bawah meniru halaman cover dokumen acuan (Fungsi/Kodifikasi,
   Katalog Proses Bisnis, tabel tim). Sel-selnya sengaja KOSONG — bukan penanda
   "(diisi manual)" — karena nilainya tidak ditanyakan di form; konvensinya sama
   dengan Revision History yang di dokumen acuan pun berupa baris kosong.
   Menambahkan penanda di sini akan menggagalkan
   test_sdd_metadata_leaves_no_manual_placeholder. #}
| Fungsi | No Kodifikasi |
|--------|------------|
| Business Relationship | |
| Business IT Solution | |

| Katalog Proses Bisnis | Kategori |
|--------|------------|
| Proses Value Chain | |
| Application Landscape | |

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

{# Tim & Peran sengaja DI HALAMAN 2, bukan di cover: diukur dari probe visual,
   cover + 3 tabel identitas + tabel tim = ~21 baris tidak muat satu halaman dan
   tabel tim terbelah jelek melintasi halaman. Cover cukup memuat identitas
   dokumen; tim & riwayat revisi satu halaman sesudahnya. #}
**Tim & Peran**

| Jabatan / Peran | Nama |
|--------|------------|
| Application Requestor | |
| Business Process Owner | |
| PIC | |
| Lead Coordinator | |
| IT Solution Analyst | |
| Developer | |
| Design UI/UX | |

## Document Revision History

| No. | Version | Revision Date | Changed By | Summary of Changes |
|:---:|------|---------|---------|------------------|
| | | | | |

## Application Revision History

| No. | Version | Revision Date | Changed By | Summary of Changes |
|:---:|------|---------|---------|------------------|
| | | | | |

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

## Persetujuan Dokumen

Dokumen ini dibuat sebagai dasar pengembangan {{ project_name }}. Jika ada perubahan dari kesepakatan waktu yang telah disetujui sebelumnya, maka lingkup perubahan dan tata waktu pekerjaan tersebut akan ditinjau kembali antara tim pengembang dengan customer aplikasi.

{# Timeline & Cost Estimation berupa KERANGKA baris kosong: sistem tidak boleh
   mengarang tanggal atau biaya. Label kelima aktivitasnya diambil dari dokumen
   acuan — itu tahapan proyek generik, bukan spesifik satu aplikasi. #}
**Timeline:**

| No. | Aktivitas | Mulai | Selesai | Deliverable |
|:---:|------------------|-------|-------|----------|
| 1 | Gathering Requirement | | | |
| 2 | Development | | | |
| 3 | Testing | | | |
| 4 | Security Test (Penetration Test) | | | |
| 5 | Closing | | | |

**Cost Estimation:**

| Project Code | Amount (IDR) |
|--------|--------|
| | |

**Perwakilan User**

| Nama | Jabatan | Tanda Tangan |
|--------|--------|--------|
| | | |
| | | |

**Perwakilan Pengembang**

| Nama | Jabatan | Tanda Tangan |
|--------|--------|--------|
| | | |
| | | |

Tanda tangan dibubuhkan pada dokumen cetak setelah dokumen ini disetujui — bagian ini tidak dapat dihasilkan oleh sistem.

{# Daftar Isi/Gambar/Tabel: field code Word yang sama persis dengan yang dulu
   ditulis Pandoc lewat --toc/--lof/--lot (instruksinya disalin apa adanya,
   sudah terbukti diisi Word saat dibuka) — cuma posisinya sekarang di sini,
   sesudah persetujuan, seperti dokumen acuan. Teks di dalam field adalah
   placeholder yang terlihat hanya kalau dokumen dibuka di pembaca yang tidak
   menjalankan field (bukan Word). #}
```{=openxml}
<w:p><w:pPr><w:pStyle w:val="TOCHeading"/></w:pPr><w:r><w:t>Daftar Isi</w:t></w:r></w:p>
<w:p><w:fldSimple w:instr=" TOC \o &quot;1-3&quot; \h \z \u "><w:r><w:t>Daftar ini diisi otomatis saat dokumen dibuka di Microsoft Word.</w:t></w:r></w:fldSimple></w:p>
<w:p><w:pPr><w:pStyle w:val="TOCHeading"/></w:pPr><w:r><w:t>Daftar Gambar</w:t></w:r></w:p>
<w:p><w:fldSimple w:instr=" TOC \h \z \t &quot;Image Caption&quot; \c "><w:r><w:t>Daftar ini diisi otomatis saat dokumen dibuka di Microsoft Word.</w:t></w:r></w:fldSimple></w:p>
<w:p><w:pPr><w:pStyle w:val="TOCHeading"/></w:pPr><w:r><w:t>Daftar Tabel</w:t></w:r></w:p>
<w:p><w:fldSimple w:instr=" TOC \h \z \t &quot;Table Caption&quot; \c "><w:r><w:t>Daftar ini diisi otomatis saat dokumen dibuka di Microsoft Word.</w:t></w:r></w:fldSimple></w:p>
```

{# Pemisah daftar-daftar dari isi dokumen. SATU-SATUNYA page break manual
   sesudah daftar: bab-bab isi dibiarkan mengalir. Page break di tiap bab akan
   menyisakan halaman setengah kosong di mana-mana, dan dokumen acuan pun tidak
   melakukannya. #}
```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

## 1. Deskripsi Aplikasi

{{ app_description }}

{# Tabel role meniru acuan: penomoran tabel isi dimulai DI SINI (Tabel 1),
   bukan di Demografi — acuan pun begitu. #}
| No. | Nama Role | Keterangan |
|:---:|--------|------------------|
{% for role in user_roles -%}
| {{ loop.index }} | {{ role.role_name }} | {{ role.description }} |
{% endfor %}

: Tabel 1 Informasi Role Pengguna

## 2. Application Dev System Type

{{ meta.dev_system_type }}

## 3. Informasi Demografi Aplikasi

| No. | Subject | Uraian | Remark |
|:---:|----------|--------------------|-----|
| 1 | Business Requestor | {{ meta.business_requestor }} | |
| 2 | Business User | {{ meta.business_user }} | |
| 3 | Projected User Number | {{ meta.projected_user_number }} | |
| 4 | Value (Rp) | {{ meta.value_rp }} | |
| 5 | Application Coverage Area | {{ meta.coverage_area }} | |
| 6 | Collaboration Profile | {{ meta.collaboration_profile }} | |
| 7 | Technology Capability | {{ meta.technology_capability }} | |

: Tabel 2 Informasi Demografi Aplikasi

## 4. System Requirement

| No. | System Requirement | Uraian |
|:---:|----------|--------------------|
{% for requirement in system_requirements -%}
| {{ loop.index }} | {{ requirement.name }} | {{ requirement.detail }} |
{% endfor %}

: Tabel 3 System Requirement

## 5. How to Access

{# Checklist 2 baris tetap — bentuk ini DIUKUR dari docx acuan (dulu satu field
   teks bebas, yang tidak pernah menyerupai tabelnya). Sama seperti checklist
   Application Security di bawah: baris tetap, jawabannya dari form. #}
| No. | How to Access | Deskripsi | Remark |
|:---:|--------------|------|--------------------------|
| 1 | Internal | {{ meta.access_internal }} | {{ meta.access_internal_remark }} |
| 2 | Published to Internet | {{ meta.access_published_internet }} | {{ meta.access_published_internet_remark }} |

: Tabel 4 How to Access

## 6. Infrastructure & Capacity Planning

{{ meta.infrastructure_capacity }}

## 7. Application Architecture

### 7.1 System Architecture

![Gambar 1 Arsitektur Sistem]({{ diagrams.system_architecture_image }}){{ diagrams.system_architecture_attr }}

### 7.2 Component Integration

![Gambar 2 Integrasi Komponen]({{ diagrams.component_integration_image }}){{ diagrams.component_integration_attr }}

## 8. Application Security

| No. | Check List | Remark |
|:---:|------------|------------|
| 1 | Penetration Test | {{ meta.security_penetration_test }} |
| 2 | Secure Coding Practice | {{ meta.security_secure_coding }} |
| 3 | Reverse Proxy | {{ meta.security_reverse_proxy }} |

: Tabel 5 Application Security

## 9. Application Features Requirement

| No. | Fitur Aplikasi | Deskripsi Fitur |
|:---:|----------|----------------------|
{% for feature in feature_requirements -%}
| {{ loop.index }} | {{ feature.feature_name }} | {{ feature.description }} |
{% endfor %}

: Tabel 6 Application Features Requirement

## 10. Flow Proses Bisnis

{{ business_flow_description }}

![Gambar 3 Flow Proses Bisnis]({{ diagrams.business_process_flow_image }}){{ diagrams.business_process_flow_attr }}

Tahapan alur proses bisnis:

{% for step in business_flow_steps %}
{{ loop.index }}. {{ step }}
{% endfor %}
{# Baris kosong di bawah WAJIB — heading berikutnya harus dipisah baris kosong
   dari list (blank_before_header), kembaran aturan di blok Acceptance Criteria. #}

## 11. Use Case

{# Diagram use case: kalau compiler memecahnya per aktor (arrows lebih jelas —
   template `default` mengaktifkannya), tampilkan satu gambar bernomor per aktor;
   kalau tidak (< 2 aktor / parse gagal) fallback ke satu diagram gabungan.
   Penomoran: use case = Gambar 4..(3+N), jadi activity di bawah memakai offset
   `use_case_figure_count` (bukan angka tetap). #}
{% if diagrams.use_case_diagrams_by_actor %}
{% for uc_dia in diagrams.use_case_diagrams_by_actor %}
![Gambar {{ loop.index + 3 }} Use Case Diagram — {{ uc_dia.actor }}]({{ uc_dia.image }}){{ uc_dia.attr }}

{% endfor %}
{% else %}
![Gambar 4 Use Case Diagram]({{ diagrams.use_case_diagram_image }}){{ diagrams.use_case_diagram_attr }}
{% endif %}

{% for uc in use_cases %}
### 11.{{ loop.index }} Use Case {{ uc.use_case_id }} — {{ uc.actor }}

| Field | Isi |
|------|--------------------|
| No. Use Case | {{ uc.use_case_id }} |
| Actor | {{ uc.actor }} |
| Pre-Condition | {{ uc.pre_condition }} |
| Description | {{ uc.description }} |

: Tabel {{ loop.index + 6 }} Use Case {{ uc.use_case_id }} — {{ uc.actor }}

{# Baris kosong di bawah WAJIB. Markdown mensyaratkan list didahului baris
   kosong; tanpa itu "1." dianggap lanjutan paragraf "Acceptance Criteria:" dan
   SELURUH kriteria dilebur jadi satu paragraf gembung — terjadi betulan, dan
   cuma ketahuan dengan membaca dokumen jadinya, bukan template-nya. #}
**Acceptance Criteria:**

{% for criterion in uc.acceptance_criteria %}
{{ loop.index }}. {{ criterion }}
{% endfor %}
{# Baris kosong di bawah juga WAJIB — sisi SEBALIKNYA dari aturan di atas.
   Pandoc mensyaratkan baris kosong SEBELUM heading (blank_before_header);
   tanpa ini "### 11.2 ..." use case berikutnya menempel di kriteria terakhir
   dan keluar sebagai TEKS LITERAL "### ..." di dalam list item, bukan heading —
   hilang dari Daftar Isi, tanpa gaya, tanpa error. Terjadi betulan pada
   use case 11.2–11.8 dokumen esteler. #}

{% endfor %}

## 12. Activity Diagram

{% for activity in diagrams.activity_diagrams %}
### 12.{{ loop.index }} {{ activity.activity_name }}

{{ activity.description }}

![Gambar {{ loop.index + 3 + diagrams.use_case_figure_count }} Activity Diagram {{ activity.activity_name }}]({{ activity.image_path }}){{ activity.image_attr }}

{# Nomor ACT ditanam deterministik dari urutan (bukan diminta ke LLM): tidak ada
   yang bisa dikarang dari penomoran, dan urutannya dijamin sinkron dengan
   heading 12.N di atasnya. #}
| Field | Isi |
|------|--------------------|
| No. Activity Diagram | ACT{{ "%03d" | format(loop.index) }} |
| Actor | {{ activity.actor }} |
| System | {{ project_name }} |
| Pre-Condition | {{ activity.pre_condition }} |

: Tabel {{ loop.index + 6 + use_cases | length }} Activity Diagram {{ activity.activity_name }}

**Description:**

{% for step in activity.steps %}
{{ loop.index }}. {{ step }}
{% endfor %}
{# Baris kosong di bawah WAJIB — pemisah list dari heading 12.N+1 berikutnya
   (blank_before_header), aturan yang sama dengan blok Acceptance Criteria. #}

{% endfor %}

{# Dokumen acuan menutup dengan dua bab mockup (Website & Aplikasi) — 43% dari
   87 halamannya. Mockup mustahil diturunkan dari kode, tapi BAB-nya tetap
   dipasang sebagai placeholder supaya struktur setara dengan acuan dan pembaca
   tahu bagian itu memang menunggu isian, bukan terlupakan. Sengaja SATU bab,
   bukan dua seperti acuan: template generik tidak tahu aplikasinya punya
   platform apa saja, dan bab kosong yang tidak relevan lebih buruk daripada
   tidak ada (pelajaran yang sama dengan Daftar Gambar UAT). #}
## 13. Mockup Antarmuka

*Tampilan antarmuka (mockup UI) tidak dapat diturunkan dari source code. Bagian ini dilengkapi manual oleh tim desain — lampirkan mockup atau tangkapan layar tiap halaman aplikasi di sini.*
