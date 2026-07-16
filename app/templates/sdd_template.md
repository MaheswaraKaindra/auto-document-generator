{#
  PENOMORAN GAMBAR & TABEL — baca ini sebelum menambah gambar/tabel.

  Nomornya ditanam langsung di teks caption ("Gambar 4 ..."), bukan dihitung
  Word. Word cuma mengumpulkan caption itu ke Daftar Gambar/Tabel dan menambahkan
  nomor HALAMAN-nya. Jadi urutan di sini WAJIB urut dokumen, dan `+3` di bawah
  adalah jumlah gambar/tabel tetap yang mendahului loop-nya:

    Gambar 1-3 tetap : Arsitektur Sistem, Integrasi Komponen, Use Case Diagram
    Gambar 4..N      : activity diagram      -> loop.index + 3
    Tabel  1-3 tetap : Demografi, Security, Features Requirement
    Tabel  4..N      : use case per aktor    -> loop.index + 3

  Menambah gambar/tabel TETAP berarti offset `+3` ikut naik — di dua tempat.
  Kalau lupa, penomorannya bentrok tanpa error apa pun.

  Ketiga gambar tetap dijamin ada: compiler mengaksesnya dengan diagrams["..."]
  (KeyError kalau hilang) dan render yang gagal melempar DiagramRenderError, jadi
  dokumen yang jadi pasti punya ketiganya — tidak ada Gambar 2 tanpa Gambar 1.

  Tabel front-matter (Informasi Dokumen, Revision History) sengaja TIDAK
  di-caption: dokumen acuan pun tidak menomorinya, dan penomoran isi dimulai
  dari Informasi Demografi.
#}
## Informasi Dokumen

| Field | Isi |
| --- | --- |
| Nama Project | {{ project_name }} |
| No. Solution Design | {{ meta.solution_design_no }} |
| RFC # | {{ meta.rfc_number }} |
| Versi | {{ meta.version }} |
| Document Classification | {{ meta.document_classification }} |

{# Tiga tabel di bawah meniru halaman muka dokumen acuan (Fungsi/Kodifikasi,
   Katalog Proses Bisnis, tabel tim). Sel-selnya sengaja KOSONG — bukan penanda
   "(diisi manual)" — karena nilainya tidak ditanyakan di form; konvensinya sama
   dengan Revision History yang di dokumen acuan pun berupa baris kosong.
   Menambahkan penanda di sini akan menggagalkan
   test_sdd_metadata_leaves_no_manual_placeholder. #}
| Fungsi | No Kodifikasi |
| --- | --- |
| Business Relationship | |
| Business IT Solution | |

| Katalog Proses Bisnis | Kategori |
| --- | --- |
| Proses Value Chain | |
| Application Landscape | |

**Tim & Peran**

| Jabatan / Peran | Nama |
| --- | --- |
| Application Requestor | |
| Business Process Owner | |
| PIC | |
| Lead Coordinator | |
| IT Solution Analyst | |
| Developer | |
| Design UI/UX | |

## Document Revision History

| No. | Version | Revision Date | Changed By | Summary of Changes |
| --- | --- | --- | --- | --- |
| | | | | |

## Application Revision History

| No. | Version | Revision Date | Changed By | Summary of Changes |
| --- | --- | --- | --- | --- |
| | | | | |

## Persetujuan Dokumen

Dokumen ini dibuat sebagai dasar pengembangan {{ project_name }}. Jika ada perubahan dari kesepakatan waktu yang telah disetujui sebelumnya, maka lingkup perubahan dan tata waktu pekerjaan tersebut akan ditinjau kembali antara tim pengembang dengan customer aplikasi.

{# Timeline & Cost Estimation berupa KERANGKA baris kosong: sistem tidak boleh
   mengarang tanggal atau biaya. Label kelima aktivitasnya diambil dari dokumen
   acuan — itu tahapan proyek generik, bukan spesifik satu aplikasi. #}
**Timeline:**

| No. | Aktivitas | Mulai | Selesai | Deliverable |
| --- | --- | --- | --- | --- |
| 1 | Gathering Requirement | | | |
| 2 | Development | | | |
| 3 | Testing | | | |
| 4 | Security Test (Penetration Test) | | | |
| 5 | Closing | | | |

**Cost Estimation:**

| Project Code | Amount (IDR) |
| --- | --- |
| | |

**Perwakilan User**

| Nama | Jabatan | Tanda Tangan |
| --- | --- | --- |
| | | |
| | | |

**Perwakilan Pengembang**

| Nama | Jabatan | Tanda Tangan |
| --- | --- | --- |
| | | |
| | | |

Tanda tangan dibubuhkan pada dokumen cetak setelah dokumen ini disetujui — bagian ini tidak dapat dihasilkan oleh sistem.

{# Pemisah halaman muka (identitas, riwayat revisi, persetujuan) dari isi
   dokumen. Pandoc tidak punya sintaks page break lintas-format, jadi dipakai
   blok mentah OpenXML — diuji, dan memang diteruskan apa adanya ke docx.
   SATU-SATUNYA page break yang dipasang: bagian lain dibiarkan mengalir. Page
   break di tiap bab akan menyisakan halaman setengah kosong di mana-mana, dan
   dokumen acuan pun tidak melakukannya. #}
```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

## 1. Deskripsi Aplikasi

{{ app_description }}

## 2. Application Dev System Type

{{ meta.dev_system_type }}

## 3. Informasi Demografi Aplikasi

| No. | Subject | Uraian | Remark |
| --- | --- | --- | --- |
| 1 | Business Requestor | {{ meta.business_requestor }} | |
| 2 | Business User | {{ meta.business_user }} | |
| 3 | Projected User Number | {{ meta.projected_user_number }} | |
| 4 | Value (Rp) | {{ meta.value_rp }} | |
| 5 | Application Coverage Area | {{ meta.coverage_area }} | |
| 6 | Collaboration Profile | {{ meta.collaboration_profile }} | |
| 7 | Technology Capability | {{ meta.technology_capability }} | |

: Tabel 1 Informasi Demografi Aplikasi

## 4. System Requirement

{% for requirement in system_requirements %}
- {{ requirement }}
{% endfor %}

## 5. How to Access

{{ meta.how_to_access }}

## 6. Infrastructure & Capacity Planning

{{ meta.infrastructure_capacity }}

## 7. Application Architecture

### 7.1 System Architecture

![Gambar 1 Arsitektur Sistem]({{ diagrams.system_architecture_image }}){{ diagrams.system_architecture_attr }}

### 7.2 Component Integration

![Gambar 2 Integrasi Komponen]({{ diagrams.component_integration_image }}){{ diagrams.component_integration_attr }}

## 8. Application Security

| No. | Check List | Remark |
| --- | --- | --- |
| 1 | Penetration Test | {{ meta.security_penetration_test }} |
| 2 | Secure Coding Practice | {{ meta.security_secure_coding }} |
| 3 | Reverse Proxy | {{ meta.security_reverse_proxy }} |

: Tabel 2 Application Security

## 9. Application Features Requirement

| No. | Fitur Aplikasi | Deskripsi Fitur |
| --- | --- | --- |
{% for feature in feature_requirements -%}
| {{ loop.index }} | {{ feature.feature_name }} | {{ feature.description }} |
{% endfor %}

: Tabel 3 Application Features Requirement

## 10. Flow Proses Bisnis

{{ business_flow_description }}

## 11. Use Case

![Gambar 3 Use Case Diagram]({{ diagrams.use_case_diagram_image }}){{ diagrams.use_case_diagram_attr }}

{% for uc in use_cases %}
### 11.{{ loop.index }} Use Case {{ uc.use_case_id }} — {{ uc.actor }}

| Field | Isi |
| --- | --- |
| No. Use Case | {{ uc.use_case_id }} |
| Actor | {{ uc.actor }} |
| Pre-Condition | {{ uc.pre_condition }} |
| Description | {{ uc.description }} |

: Tabel {{ loop.index + 3 }} Use Case {{ uc.use_case_id }} — {{ uc.actor }}

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

![Gambar {{ loop.index + 3 }} Activity Diagram {{ activity.activity_name }}]({{ activity.image_path }}){{ activity.image_attr }}

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
