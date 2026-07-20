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
    5. DUA bab mockup (Website & Aplikasi) — dokumen aslinya memang dua.

    6. How to Access & Infrastructure & Capacity Planning berbentuk TABEL
       (diukur dari docx asli): How to Access = checklist 2 baris tetap dengan
       kolom Deskripsi (YES/NO) + Remark; Infrastructure = kerangka 22 baris
       KOSONG (Akses URL/Server/DB/Web Service/Background Job per environment,
       Team Foundation Server) — isinya URL deployment, jadi manual seperti
       Timeline & Cost Estimation, bukan field form.

  PENOMORAN (aturan yang sama dengan sdd_template.md — nomor ditanam di caption,
  urutan wajib urut dokumen, offset = jumlah gambar/tabel tetap sebelum loop):
    Gambar 1-2 tetap : Arsitektur, Flow Proses Bisnis
    Gambar 3..(2+K)  : use case (K=use_case_figure_count: 1 diagram tunggal, atau
                       satu per aktor kalau compiler memecahnya — panah lebih jelas)
    Gambar (3+K)..N  : activity diagram      -> loop.index + 2 + use_case_figure_count
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
| Field | Isi |
|----------|--------------------|
| Nama Project | {{ project_name }} |
| No. Solution Design | {{ meta.solution_design_no }} |
| RFC # | {{ meta.rfc_number }} |
| Versi | {{ meta.version }} |
| Document Classification | {{ meta.document_classification }} |

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

```{=openxml}
<w:p><w:pPr><w:pStyle w:val="TOCHeading"/></w:pPr><w:r><w:t>Daftar Isi</w:t></w:r></w:p>
<w:p><w:fldSimple w:instr=" TOC \o &quot;1-3&quot; \h \z \u "><w:r><w:t>Daftar ini diisi otomatis saat dokumen dibuka di Microsoft Word.</w:t></w:r></w:fldSimple></w:p>
<w:p><w:pPr><w:pStyle w:val="TOCHeading"/></w:pPr><w:r><w:t>Daftar Gambar</w:t></w:r></w:p>
<w:p><w:fldSimple w:instr=" TOC \h \z \t &quot;Image Caption&quot; \c "><w:r><w:t>Daftar ini diisi otomatis saat dokumen dibuka di Microsoft Word.</w:t></w:r></w:fldSimple></w:p>
<w:p><w:pPr><w:pStyle w:val="TOCHeading"/></w:pPr><w:r><w:t>Daftar Tabel</w:t></w:r></w:p>
<w:p><w:fldSimple w:instr=" TOC \h \z \t &quot;Table Caption&quot; \c "><w:r><w:t>Daftar ini diisi otomatis saat dokumen dibuka di Microsoft Word.</w:t></w:r></w:fldSimple></w:p>
```

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

## Deskripsi Aplikasi

{{ app_description }}

| No. | Nama Role | Keterangan |
|:---:|--------|------------------|
{% for role in user_roles -%}
| {{ loop.index }} | {{ role.role_name }} | {{ role.description }} |
{% endfor %}

: Tabel 1 Informasi Role Pengguna

## Application Dev System Type

{{ meta.dev_system_type }}

## Informasi Demografi Aplikasi

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
## System Requirement

| No. | System Requirement | Uraian | Remark |
|:---:|----------|------------------|-----|
{% for requirement in system_requirements -%}
| {{ loop.index }} | {{ requirement.name }} | {{ requirement.detail }} | |
{% endfor %}

: Tabel 3 System Requirement

## How to Access

| No. | How to Access | Deskripsi | Remark |
|:---:|--------------|------|--------------------------|
| 1 | Internal | {{ meta.access_internal }} | {{ meta.access_internal_remark }} |
| 2 | Published to Internet | {{ meta.access_published_internet }} | {{ meta.access_published_internet_remark }} |

: Tabel 4 How to Access

## Infrastructure & Capacity Planning

{# Kerangka KOSONG, meniru dokumen asli: 22 baris, kolom Remark berisi URL &
   kapasitas deployment — tidak diturunkan dari kode dan tidak ditanyakan form
   (lihat schemas_document.py). Kolom No./Resources sengaja dikosongkan pada
   baris lanjutan: itu tiruan sel ter-merge vertikal dokumen asli, yang tidak
   bisa dinyatakan pipe table. Sel kosong, BUKAN `(diisi manual)` — sama dengan
   konvensi Timeline & Cost Estimation di bab Persetujuan. #}
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

## Application Architecture

![Gambar 1 Arsitektur Sistem]({{ diagrams.system_architecture_image }}){{ diagrams.system_architecture_attr }}

## Application Security

| No. | Check List | Remark |
|:---:|------------|------------|
| 1 | Penetration Test | {{ meta.security_penetration_test }} |
| 2 | Secure Coding Practice | {{ meta.security_secure_coding }} |
| 3 | Reverse Proxy | {{ meta.security_reverse_proxy }} |

: Tabel 6 Application Security

## Application Features Requirement

| No. | Fitur Aplikasi | Deskripsi Fitur | Remark |
|:---:|----------|----------------------|----|
{% for feature in feature_requirements -%}
| {{ loop.index }} | {{ feature.feature_name }} | {{ feature.description }} | |
{% endfor %}

: Tabel 7 Application Features Requirement

## Flow Proses Bisnis

{{ business_flow_description }}

![Gambar 2 Flow Proses Bisnis]({{ diagrams.business_process_flow_image }}){{ diagrams.business_process_flow_attr }}

Tahapan alur proses bisnis:

{% for step in business_flow_steps %}
{{ loop.index }}. {{ step }}
{% endfor %}
{# Baris kosong di bawah WAJIB — pemisah list dari heading (blank_before_header). #}

## Use Case

{# Diagram use case dipecah per aktor kalau compiler mengaktifkannya (panah lebih
   jelas); fallback ke satu diagram gabungan kalau tidak (< 2 aktor / parse gagal).
   Use case = Gambar 3..(2+K); activity di bawah pakai offset use_case_figure_count. #}
{% if diagrams.use_case_diagrams_by_actor %}
{% for uc_dia in diagrams.use_case_diagrams_by_actor %}
![Gambar {{ loop.index + 2 }} Use Case Diagram — {{ uc_dia.actor }}]({{ uc_dia.image }}){{ uc_dia.attr }}

{% endfor %}
{% else %}
![Gambar 3 Use Case Diagram]({{ diagrams.use_case_diagram_image }}){{ diagrams.use_case_diagram_attr }}
{% endif %}

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

## Activity Diagram

{% for activity in diagrams.activity_diagrams %}
{{ activity.description }}

![Gambar {{ loop.index + 2 + diagrams.use_case_figure_count }} Activity Diagram {{ activity.activity_name }}]({{ activity.image_path }}){{ activity.image_attr }}

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

{# Dokumen aslinya menutup dengan DUA bab mockup — Website dan Aplikasi.
   Keduanya placeholder manual: mockup mustahil diturunkan dari kode. #}
## Mockup Website

*Tampilan antarmuka website (mockup UI) tidak dapat diturunkan dari source code. Bagian ini dilengkapi manual oleh tim desain.*

## Mockup Aplikasi

*Tampilan antarmuka aplikasi (mockup UI) tidak dapat diturunkan dari source code. Bagian ini dilengkapi manual oleh tim desain.*
