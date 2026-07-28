{#
  TEMPLATE "PREMCO" — hasil KOMPILASI MANUAL dari docx PREMCO asli (V1 roadmap
  tahap c; pengukurannya di scripts/validation/V0_TEMPLATE_PREMCO.md).
  Perbedaan yang DISENGAJA terhadap sdd_template.md (default), semuanya
  konvensi yang terukur dari dokumen aslinya:

    1. Heading bab TANPA nomor ("Deskripsi Aplikasi", bukan "1. Deskripsi...")
       — bab dokumen aslinya tidak bernomor.
    2. Tabel use case & activity memakai BAR JUDUL biru (baris pertama ditandai
       ((BAR)) — post-process compiler yang me-merge sel + mewarnai 9CC3E5,
       warna terukur dari 27 sel dokumen asli). Acceptance criteria & langkah
       activity ada DI DALAM tabel (dipisah <br/>), bukan list di luar.
    3. TIDAK ada Component Integration — dokumen aslinya cuma punya satu gambar
       arsitektur. (Aturan V1: template MENGISI, tidak merestrukturisasi; slot
       yang tidak ada di-drop, bukan dikarang.)
    4. Tabel Features membawa kolom Remark kosong (konvensi dokumen asli).
    5. DUA mockup (Website & Aplikasi) — dokumen aslinya memang dua. Keduanya kini
       SUB-BAB (Heading 2, bernomor 3 & 4) di bawah Flow Proses Bisnis, bukan bab
       tersendiri — bersama Use Case (1) & Activity Diagram (2). Meniru Daftar Isi
       docx asli (2026-07-21 lanjutan 10).

    7. COVER & BLOK TANDA TANGAN gaya PREMCO (2026-07-21 lanjutan 10, permintaan
       pemilik "persis docx PREMCO"): cover = tiga tabel berbingkai header gelap
       (Fungsi/Kodifikasi, Katalog, Entitas/Jabatan/Nama) — BUKAN cover minimalis
       borderless ((CVBAND))/((CVLIST)) milik `default`. Kolom Entitas di-merge
       vertikal (marker ((CVMERGE))). Perwakilan User/Pengembang = bar judul HITAM
       selebar tabel + 2 kolom × 2 baris (marker ((SIGBAR))). Detail di compiler.
       Lanjutan 11: blok judul cover (eyebrow + judul + baris identitas) di-align
       KANAN oleh compiler (`_right_align_cover`, flag `cover_align_right` premco).

    6. How to Access & Infrastructure & Capacity Planning berbentuk TABEL
       (diukur dari docx asli): How to Access = checklist 2 baris tetap dengan
       kolom Deskripsi (YES/NO) + Remark; Infrastructure = kerangka 22 baris
       KOSONG (Akses URL/Server/DB/Web Service/Background Job per environment,
       Team Foundation Server) — isinya URL deployment, jadi manual seperti
       Timeline & Cost Estimation, bukan field form.

  PENOMORAN (aturan yang sama dengan sdd_template.md — nomor ditanam di caption,
  urutan wajib urut dokumen, offset = jumlah gambar/tabel tetap sebelum loop):
    Gambar 1-2 tetap : Arsitektur, Flow Proses Bisnis
    Gambar 3 tetap   : Use Case Diagram (SATU diagram gabungan)
    Gambar 4..N      : activity diagram      -> loop.index + 3
    Tabel  1-7 tetap : Role, Demografi, System Requirement, How to Access,
                       Infrastructure, Security, Features
    Tabel  8..N      : use case              -> loop.index + 7
    Tabel  N+1..     : activity diagram      -> loop.index + 7 + use_cases|length

  Catatan silang: di docx asli How to Access = "Tabel 5" dan Infrastructure =
  "Tabel 6", sementara di sini 4 dan 5. Selisih 1 itu BUKAN salah hitung —
  System Requirement mereka DUA tabel (Server Side 1 & 2) sedangkan kita masih
  satu. Begitu gap itu ditutup (butuh Contract B), penomoran ini otomatis sama
  persis dengan aslinya.
#}
{# ================= HALAMAN COVER =================
   Cover gaya PREMCO — DIUKUR dari halaman 1 docx aslinya (ref/benchmark):
   label jenis dokumen + nama project (dari --metadata title, dipecah compiler
   `_split_cover_title`), lalu identitas (No/Versi/RFC/Klasifikasi), baru TIGA
   tabel header-gelap: Fungsi/Kodifikasi, Katalog Proses Bisnis, dan Tim Project
   (Entitas | Jabatan | Nama).

   Berbeda dari template `default` (yang memakai cover minimalis TANPA kotak
   lewat marker ((CVBAND))/((CVLIST))): di sini pemilik project minta cover
   PERSIS PREMCO — tabel berbingkai header gelap. Jadi blok-blok ini ditulis
   sebagai pipe table BIASA; style tabel bawaan reference.docx sudah memberi
   baris header latar hitam + teks putih (fill PREMCO 3b3838/252525 praktis sama
   dengan hitam). Tak butuh marker khusus KECUALI kolom Entitas yang di dokumen
   asli di-merge vertikal — ditandai ((CVMERGE)), compiler yang menggabungnya. #}
::: {custom-style="Cover Subtitle"}
No. Solution Design {{ meta.solution_design_no }}  ·  Versi {{ meta.version }}
:::

::: {custom-style="Cover Subtitle"}
RFC # {{ meta.rfc_number }}  ·  Document Classification: {{ meta.document_classification }}
:::

::: {custom-style="Cover Rule"}
&nbsp;
:::

| Fungsi | No Kodifikasi |
|------------------------|------------------|
| Business Relationship | {{ meta.business_relationship_no }} |
| Business IT Solution | {{ meta.business_it_solution_no }} |

| Katalog Proses Bisnis | No. Kategori Proses |
|------------------------|------------------|
| Value Chain | {{ meta.value_chain }} |
| Application Landscape | {{ meta.application_landscape }} |

| ((CVMERGE))Entitas | Jabatan | Nama |
|------------------|------------------------|------------------------|
| {{ meta.entitas }} | Application Requestor | {{ meta.team_application_requestor }} |
|  | Business Process Owner | {{ meta.team_business_process_owner }} |
|  | PIC | {{ meta.team_pic }} |
|  | Lead Coordinator | {{ meta.team_lead_coordinator }} |
|  | IT Solution Analyst | {{ meta.team_it_solution_analyst }} |
|  | Developer | {{ meta.team_developer }} |
|  | Design UI/UX | {{ meta.team_design_uiux }} |

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

# Document Revision History

| No. | Version | Revision Date | Changed By | Summary of Changes |
|:---:|------|---------|---------|------------------|
| | | | | |

# Application Revision History

| No. | Version | Revision Date | Changed By | Summary of Changes |
|:---:|------|---------|---------|------------------|
| | | | | |

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

# Persetujuan Dokumen

Dokumen ini dibuat sebagai dasar pengembangan {{ project_name }}. Jika ada perubahan dari kesepakatan waktu yang telah disetujui sebelumnya, maka lingkup perubahan dan tata waktu pekerjaan tersebut akan ditinjau kembali antara tim pengembang dengan customer aplikasi.

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

{# Blok tanda tangan gaya PREMCO (diukur dari docx asli): bar judul HITAM
   selebar tabel (baris pertama ditandai ((SIGBAR)) — compiler me-merge sel +
   mewarnai 000000 + teks putih), lalu 2 kolom × 2 baris (ruang tanda tangan di
   atas, nama/jabatan di bawah). Nama sengaja KOSONG: dibubuhkan tangan setelah
   dokumen disetujui, bukan data yang bisa dihasilkan sistem. #}
| ((SIGBAR))Perwakilan User | |
|:------:|:------:|
| | |
| | |

| ((SIGBAR))Perwakilan Pengembang | |
|:------:|:------:|
| | |
| | |

Tanda tangan dibubuhkan pada dokumen cetak setelah dokumen ini disetujui — bagian ini tidak dapat dihasilkan oleh sistem.

{# Judul ketiga daftar memakai `Heading1`, BUKAN `TOCHeading` seperti template
   `default`. Bukan selera: dokumen PREMCO asli menaruhnya sebagai Heading 1
   sehingga ketiganya IKUT TERDAFTAR di Daftar Isi — diverifikasi ke PDF acuan
   halaman 5, yang memuat baris "DAFTAR ISI…", "DAFTAR GAMBAR…", "DAFTAR TABEL…"
   di antara PERSETUJUAN DOKUMEN dan DESKRIPSI APLIKASI. Dengan `TOCHeading`
   (gaya Word standar, sengaja tak masuk daftar) ketiganya hilang dari Daftar Isi
   dan urutan bab kita menyimpang dari acuan. `default` sengaja TETAP memakai
   `TOCHeading` — dia bukan tiruan PREMCO. #}
```{=openxml}
<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Daftar Isi</w:t></w:r></w:p>
<w:p><w:fldSimple w:instr=" TOC \o &quot;1-3&quot; \h \z \u "><w:r><w:t>Daftar ini terisi otomatis saat field diperbarui — di Word tekan Ctrl+A lalu F9, atau klik kanan di sini &gt; Update Field.</w:t></w:r></w:fldSimple></w:p>
<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Daftar Gambar</w:t></w:r></w:p>
<w:p><w:fldSimple w:instr=" TOC \h \z \t &quot;Image Caption&quot; \c "><w:r><w:t>Daftar ini terisi otomatis saat field diperbarui — di Word tekan Ctrl+A lalu F9, atau klik kanan di sini &gt; Update Field.</w:t></w:r></w:fldSimple></w:p>
<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Daftar Tabel</w:t></w:r></w:p>
<w:p><w:fldSimple w:instr=" TOC \h \z \t &quot;Table Caption&quot; \c "><w:r><w:t>Daftar ini terisi otomatis saat field diperbarui — di Word tekan Ctrl+A lalu F9, atau klik kanan di sini &gt; Update Field.</w:t></w:r></w:fldSimple></w:p>
```

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

# Deskripsi Aplikasi

{{ app_description }}

| No. | Nama Role | Keterangan |
|:---:|--------|------------------|
{% for role in user_roles -%}
| {{ loop.index }} | {{ role.role_name }} | {{ role.description }} |
{% endfor %}

: Tabel 1 Informasi Role Pengguna

# Application Dev System Type

{{ meta.dev_system_type }}

# Informasi Demografi Aplikasi

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

{# Kolom Remark ditambahkan supaya 4-kolom seperti dokumen asli (di sana kolom
   Remark memang mayoritas kosong — cuma terisi di 2 dari 7 baris). SATU tabel,
   BUKAN dua: dokumen asli memecah jadi "Server Side 1" (backend/runtime) &
   "Server Side 2" (kompatibilitas Browser/Android), tapi tabel kedua itu ISINYA
   TIDAK DAPAT diturunkan dari kode — kompatibilitas browser/OS itu keputusan
   deployment, bukan sesuatu yang ada di source. Aturan V1 (mengisi, bukan
   mengarang; slot tanpa data DI-DROP) → tabel kedua tidak dibuat. #}
# System Requirement

| No. | System Requirement | Uraian | Remark |
|:---:|----------|------------------|-----|
{% for requirement in system_requirements -%}
| {{ loop.index }} | {{ requirement.name }} | {{ requirement.detail }} | |
{% endfor %}

: Tabel 3 System Requirement

# How to Access

| No. | How to Access | Deskripsi | Remark |
|:---:|--------------|------|--------------------------|
| 1 | Internal | {{ meta.access_internal }} | {{ meta.access_internal_remark }} |
| 2 | Published to Internet | {{ meta.access_published_internet }} | {{ meta.access_published_internet_remark }} |

: Tabel 4 How to Access

# Infrastructure & Capacity Planning

{# Kerangka KOSONG, meniru dokumen asli: 22 baris, kolom Remark berisi URL &
   kapasitas deployment — tidak diturunkan dari kode dan tidak ditanyakan form
   (lihat schemas_document.py). Kolom No./Resources sengaja dikosongkan pada
   baris lanjutan: itu tiruan sel ter-merge vertikal dokumen asli, yang tidak
   bisa dinyatakan pipe table. Sel kosong, BUKAN `(diisi manual)` — sama dengan
   konvensi Timeline & Cost Estimation di bab Persetujuan.
   Baris yang kolom sub-environment (idx 2) & Remark (idx 3) DUA-DUANYA kosong
   (Infrastructure Tech Req, Network, Data Center) digabung jadi satu sel lebar
   oleh compiler (`_merge_infra_empty_cells`) — meniru docx asli; baris ber-sub-env
   (Akses URL → Development/QA) tetap terpisah. #}
| No. | Resources | | Remark |
|:---:|-----------------|------------|--------------------|
| 1 | Infrastructure Technology Requirement | | |
| 2 | Network | | |
| 3 | Data Center | | |
| 4 | Akses URL | Development | |
| | | QA | |
| | | Prod | |
| | | Internal Rev. Proxy | |
| | | External Rev. Proxy | |
| 5 | Server | Development | |
| | | QA | |
| | | Production | |
| 6 | Database Server | Development | |
| | | QA | |
| | | Production | |
| 7 | Web Service | Development | |
| | | QA | |
| | | Production | |
| 8 | Background Job | Development | |
| | | QA | |
| | | Production | |
| 9 | Team Foundation Server | Location | |
| | | Project Name | |

: Tabel 5 Infrastructure and Capacity Planning

# Application Architecture

![Gambar 1 Arsitektur Sistem]({{ diagrams.system_architecture_image }}){{ diagrams.system_architecture_attr }}

# Application Security

| No. | Check List | Remark |
|:---:|------------|------------|
| 1 | Penetration Test | {{ meta.security_penetration_test }} |
| 2 | Secure Coding Practice | {{ meta.security_secure_coding }} |
| 3 | Reverse Proxy | {{ meta.security_reverse_proxy }} |

: Tabel 6 Application Security

# Application Features Requirement

| No. | Fitur Aplikasi | Deskripsi Fitur | Remark |
|:---:|----------|----------------------|----|
{% for feature in feature_requirements -%}
| {{ loop.index }} | {{ feature.feature_name }} | {{ feature.description }} | |
{% endfor %}

: Tabel 7 Application Features Requirement

# Flow Proses Bisnis

{{ business_flow_description }}

![Gambar 2 Flow Proses Bisnis]({{ diagrams.business_process_flow_image }}){{ diagrams.business_process_flow_attr }}

Tahapan alur proses bisnis:

{% for step in business_flow_steps %}
{{ loop.index }}. {{ step }}
{% endfor %}
{# Baris kosong di bawah WAJIB — pemisah list dari heading (blank_before_header). #}

{# Use Case, Activity Diagram, dan dua Mockup adalah SUB-BAB (Heading 2, bernomor
   1-4) di bawah "Flow Proses Bisnis" — hierarki & penomoran DIUKUR dari Daftar
   Isi docx PREMCO asli (bab utama tanpa nomor, sub-bab ber-nomor 1..4). Nomornya
   ditulis manual di teks heading; Word menampilkannya apa adanya di Daftar Isi.
   TOC \o "1-3" tetap mengoleksi Heading 2 ini (terindentasi di bawah babnya). #}
## 1. Use Case

{# SATU diagram use case gabungan (semua aktor dalam satu gambar). Gambar 3 tetap;
   activity di bawah mulai Gambar 4 (loop.index + 3). #}
![Gambar 3 Use Case Diagram]({{ diagrams.use_case_diagram_image }}){{ diagrams.use_case_diagram_attr }}

{% for uc in use_cases %}
| ((BAR))Use Case {{ uc.use_case_id }} — {{ uc.actor }} | |
|------|--------------------|
| No. Use Case | {{ uc.use_case_id }} |
| Actor | {{ uc.actor }} |
| Pre-Condition | {{ uc.pre_condition }} |
| Description | {{ uc.description }} |
| Acceptance Criteria | {% for c in uc.acceptance_criteria %}{{ loop.index }}. {{ c }}{% if not loop.last %}((BR)){% endif %}{% endfor %} |

: Tabel {{ loop.index + 7 }} Use Case {{ uc.use_case_id }} — {{ uc.actor }}

{% endfor %}

## 2. Activity Diagram

{% for activity in diagrams.activity_diagrams %}
{# Tiap activity diagram jadi SUB-BAB tersendiri (Heading 3, bernomor manual
   "2.N" seperti bab lain di premco yang menomori sendiri — bukan auto-number
   Word). Meniru dokumen PREMCO asli yang memecah "Activity Diagram Login –
   Website", "… Mobile", dst. jadi bagian terpisah. Heading 3 masuk Daftar Isi
   (field TOC \o "1-3") — keputusan pemilik: sub-bab ini MUNCUL di Daftar Isi. #}
### 2.{{ loop.index }} Activity Diagram {{ activity.activity_name }}

{{ activity.description }}

![Gambar {{ loop.index + 3 }} Activity Diagram {{ activity.activity_name }}]({{ activity.image_path }}){{ activity.image_attr }}

{# Langkah aktivitas ada DI DALAM sel Description (konvensi dokumen asli),
   dipisah marker ((BR)) yang ditukar post-process jadi line break sungguhan —
   `<br/>` TIDAK bisa dipakai: writer docx Pandoc membuang raw HTML tanpa suara. #}
| ((BAR))Activity Diagram {{ activity.activity_name }} | |
|------|--------------------|
| No. Activity Diagram | ACT{{ "%03d" | format(loop.index) }} |
| Actor | {{ activity.actor }} |
| System | {{ project_name }} |
| Pre-Condition | {{ activity.pre_condition }} |
| Description | {% for step in activity.steps %}{{ loop.index }}. {{ step }}{% if not loop.last %}((BR)){% endif %}{% endfor %} |

: Tabel {{ loop.index + 7 + use_cases | length }} Activity Diagram {{ activity.activity_name }}

{% endfor %}

{# Dokumen aslinya menutup dengan DUA sub-bab mockup — Website dan Aplikasi
   (sub-bab 3 & 4 di bawah Flow Proses Bisnis, sesuai Daftar Isi asli). Keduanya
   placeholder manual: mockup mustahil diturunkan dari kode. #}
## 3. Mockup Website

*Tampilan antarmuka website (mockup UI) tidak dapat diturunkan dari source code. Bagian ini dilengkapi manual oleh tim desain.*

## 4. Mockup Aplikasi

*Tampilan antarmuka aplikasi (mockup UI) tidak dapat diturunkan dari source code. Bagian ini dilengkapi manual oleh tim desain.*
