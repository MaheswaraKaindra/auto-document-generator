"""Schema khusus endpoint dokumen (Peran 3). Tidak mengubah app/api/schemas.py
milik Peran 1 — file terpisah supaya tidak ada resiko konflik/campur tanggung jawab."""

from typing import Optional

from pydantic import BaseModel, Field


class GithubRepoIn(BaseModel):
    repo_tag: str
    repo_url: str
    branch: Optional[str] = None


class ZipFileIn(BaseModel):
    """Satu repo yang di-upload sebagai ZIP (base64), untuk jalur ZIP -> dokumen.

    Base64-in-JSON, pola yang sama dengan `logo_base64`: menyatu dengan kontrak
    JSON `/documents/generate` yang sudah ada, jadi tak perlu endpoint multipart
    terpisah. Prefiks data-URL ("data:application/zip;base64,...") dari browser
    boleh ikut — endpoint yang membuangnya."""

    repo_tag: str
    filename: str
    zip_base64: str


class DocumentMetadata(BaseModel):
    """Bagian dokumen yang manusianya tahu tapi kode tidak akan pernah tahu —
    nomor RFC, klasifikasi, data demografi, remark security.

    SENGAJA TERPISAH DARI DocumentContent (Contract B). Contract B itu kontrak
    *output LLM*; ini *input manusia*. Arahnya berlawanan, jadi jangan dicampur:
    LLM tidak boleh mengarang nomor RFC, dan pengguna tidak menulis use case.

    Semua field opsional. Yang dibiarkan kosong jatuh balik ke penanda
    *(diisi manual)* seperti sebelum form ini ada — jadi tidak mengisi apa pun
    menghasilkan dokumen persis versi lama, bukan error.
    """

    # -- Dipakai SDD --
    solution_design_no: Optional[str] = None
    rfc_number: Optional[str] = None
    version: Optional[str] = None
    document_classification: Optional[str] = None
    dev_system_type: Optional[str] = None

    # Informasi Demografi Aplikasi (bab 3 SDD)
    business_requestor: Optional[str] = None
    business_user: Optional[str] = None
    projected_user_number: Optional[str] = None
    value_rp: Optional[str] = None
    coverage_area: Optional[str] = None
    collaboration_profile: Optional[str] = None
    technology_capability: Optional[str] = None

    # How to Access (bab 5 SDD) — di dokumen acuan ini TABEL checklist 2 baris
    # tetap (Internal, Published to Internet), tiap baris punya kolom Deskripsi
    # (YES/NO) + Remark. Diukur dari docx acuan, bukan ditebak. Dulu satu field
    # teks bebas `how_to_access`, yang tidak pernah bisa menyerupai tabel itu.
    access_internal: Optional[str] = None
    access_internal_remark: Optional[str] = None
    access_published_internet: Optional[str] = None
    access_published_internet_remark: Optional[str] = None

    # Infrastructure & Capacity Planning (bab 6 SDD). Template `default` memakai
    # field teks bebas ini. Template `premco` TIDAK: dokumen acuan memakai
    # kerangka 22 baris dengan taksonomi khas perusahaannya (Akses URL per
    # environment, Rev. Proxy, Team Foundation Server) yang isinya URL deployment
    # — tidak diturunkan dari kode dan terlalu spesifik untuk template generik,
    # jadi di sana ia jadi kerangka kosong seperti Timeline & Cost Estimation.
    infrastructure_capacity: Optional[str] = None

    # Checklist Application Security (bab 8 SDD)
    security_penetration_test: Optional[str] = None
    security_secure_coding: Optional[str] = None
    security_reverse_proxy: Optional[str] = None

    # -- Dipakai UAT --
    related_rfc_number: Optional[str] = None
    related_work_order: Optional[str] = None
    change_owner: Optional[str] = None
    prepared_by: Optional[str] = None
    preparation_date: Optional[str] = None
    reviewed_by: Optional[str] = None
    review_date: Optional[str] = None
    distribution_list: Optional[str] = None

    # Document Information tambahan yang muncul di UAT PREMCO asli (template
    # `premco` UAT). Semua data manusia — tak diturunkan dari kode; kosong =
    # jatuh ke penanda *(diisi manual)* seperti field metadata lain.
    quality_review_method: Optional[str] = None
    document_version_no: Optional[str] = None
    document_version_date: Optional[str] = None


class GenerateDocumentRequest(BaseModel):
    """Body untuk endpoint orkestrator penuh: POST /documents/generate."""

    project_name: Optional[str] = None
    document_type: str  # "SDD" atau "UAT"
    github_token: Optional[str] = None
    # Sumber kode. Dua jalur yang saling menggantikan: `repositories` (GitHub)
    # ATAU `zip_files` (upload ZIP base64). Kalau `zip_files` diisi, ITU yang
    # dipakai; kalau tidak, jatuh ke `repositories`. Keduanya default kosong
    # (dibiarkan longgar: request lama yang mengirim `repositories: []` tetap sah).
    repositories: list[GithubRepoIn] = Field(default_factory=list)
    zip_files: Optional[list[ZipFileIn]] = None
    document_metadata: Optional[DocumentMetadata] = None
    # Gaya dokumen. DEFAULT-nya "premco" (meniru konvensi dokumen PREMCO/Pertamina
    # — tabel use case biru menyatu; menyediakan SDD & UAT), karena instance ini
    # premco-first. "default" = gaya acuan enterprise netral (header hitam) tetap
    # tersedia sebagai pilihan, begitu pula id template hasil upload lewat
    # POST /templates. Divalidasi sinkron di endpoint; kombinasi tak tersedia = 422.
    template_id: str = "premco"
    # Logo perusahaan (PNG/JPEG, base64) — muncul di header TIAP halaman dokumen,
    # seperti dokumen acuan enterprise. SENGAJA bukan field DocumentMetadata:
    # kontrak metadata itu "string yang jatuh ke penanda (diisi manual) kalau
    # kosong", sementara logo itu biner yang jatuh ke "tanpa header" — perilaku
    # kosongnya beda, jadi jangan dicampur. Divalidasi sinkron di endpoint
    # (decode_logo) supaya file rusak ditolak 422 SEBELUM ada kerja berbayar.
    logo_base64: Optional[str] = None
