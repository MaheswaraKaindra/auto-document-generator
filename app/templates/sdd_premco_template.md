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

  PENOMORAN (aturan yang sama dengan sdd_template.md — nomor ditanam di caption,
  urutan wajib urut dokumen, offset = jumlah gambar/tabel tetap sebelum loop):
    Gambar 1-3 tetap : Arsitektur, Flow Proses Bisnis, Use Case Diagram
    Gambar 4..N      : activity diagram      -> loop.index + 3
    Tabel  1-5 tetap : Role, Demografi, System Requirement, Security, Features
    Tabel  6..N      : use case              -> loop.index + 5
    Tabel  N+1..     : activity diagram      -> loop.index + 5 + use_cases|length
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

## System Requirement

| No. | System Requirement | Uraian |
|:---:|----------|--------------------|
{% for requirement in system_requirements -%}
| {{ loop.index }} | {{ requirement.name }} | {{ requirement.detail }} |
{% endfor %}

: Tabel 3 System Requirement

## How to Access

{{ meta.how_to_access }}

## Infrastructure & Capacity Planning

{{ meta.infrastructure_capacity }}

## Application Architecture

![Gambar 1 Arsitektur Sistem]({{ diagrams.system_architecture_image }}){{ diagrams.system_architecture_attr }}

## Application Security

| No. | Check List | Remark |
|:---:|------------|------------|
| 1 | Penetration Test | {{ meta.security_penetration_test }} |
| 2 | Secure Coding Practice | {{ meta.security_secure_coding }} |
| 3 | Reverse Proxy | {{ meta.security_reverse_proxy }} |

: Tabel 4 Application Security

## Application Features Requirement

| No. | Fitur Aplikasi | Deskripsi Fitur | Remark |
|:---:|----------|----------------------|----|
{% for feature in feature_requirements -%}
| {{ loop.index }} | {{ feature.feature_name }} | {{ feature.description }} | |
{% endfor %}

: Tabel 5 Application Features Requirement

## Flow Proses Bisnis

{{ business_flow_description }}

![Gambar 2 Flow Proses Bisnis]({{ diagrams.business_process_flow_image }}){{ diagrams.business_process_flow_attr }}

Tahapan alur proses bisnis:

{% for step in business_flow_steps %}
{{ loop.index }}. {{ step }}
{% endfor %}
{# Baris kosong di bawah WAJIB — pemisah list dari heading (blank_before_header). #}

## Use Case

![Gambar 3 Use Case Diagram]({{ diagrams.use_case_diagram_image }}){{ diagrams.use_case_diagram_attr }}

{% for uc in use_cases %}
| ((BAR))Use Case {{ uc.use_case_id }} — {{ uc.actor }} | |
|------|--------------------|
| No. Use Case | {{ uc.use_case_id }} |
| Actor | {{ uc.actor }} |
| Pre-Condition | {{ uc.pre_condition }} |
| Description | {{ uc.description }} |
| Acceptance Criteria | {% for c in uc.acceptance_criteria %}{{ loop.index }}. {{ c }}{% if not loop.last %}((BR)){% endif %}{% endfor %} |

: Tabel {{ loop.index + 5 }} Use Case {{ uc.use_case_id }} — {{ uc.actor }}

{% endfor %}

## Activity Diagram

{% for activity in diagrams.activity_diagrams %}
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

: Tabel {{ loop.index + 5 + use_cases | length }} Activity Diagram {{ activity.activity_name }}

{% endfor %}

{# Dokumen aslinya menutup dengan DUA bab mockup — Website dan Aplikasi.
   Keduanya placeholder manual: mockup mustahil diturunkan dari kode. #}
## Mockup Website

*Tampilan antarmuka website (mockup UI) tidak dapat diturunkan dari source code. Bagian ini dilengkapi manual oleh tim desain.*

## Mockup Aplikasi

*Tampilan antarmuka aplikasi (mockup UI) tidak dapat diturunkan dari source code. Bagian ini dilengkapi manual oleh tim desain.*
