"""Schema khusus endpoint dokumen (Peran 3). Tidak mengubah app/api/schemas.py
milik Peran 1 — file terpisah supaya tidak ada resiko konflik/campur tanggung jawab."""

from typing import Optional

from pydantic import BaseModel


class GithubRepoIn(BaseModel):
    repo_tag: str
    repo_url: str
    branch: Optional[str] = None


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

    how_to_access: Optional[str] = None
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


class GenerateDocumentRequest(BaseModel):
    """Body untuk endpoint orkestrator penuh: POST /documents/generate."""

    project_name: Optional[str] = None
    document_type: str  # "SDD" atau "UAT"
    github_token: Optional[str] = None
    repositories: list[GithubRepoIn]
    document_metadata: Optional[DocumentMetadata] = None
    # Gaya dokumen: "default" (template bawaan) atau "premco" (kompilasi manual
    # docx PREMCO, V1 roadmap tahap c — baru menyediakan SDD). Divalidasi
    # sinkron di endpoint; kombinasi yang tidak tersedia = 422.
    template_id: str = "default"
    # Logo perusahaan (PNG/JPEG, base64) — muncul di header TIAP halaman dokumen,
    # seperti dokumen acuan enterprise. SENGAJA bukan field DocumentMetadata:
    # kontrak metadata itu "string yang jatuh ke penanda (diisi manual) kalau
    # kosong", sementara logo itu biner yang jatuh ke "tanpa header" — perilaku
    # kosongnya beda, jadi jangan dicampur. Divalidasi sinkron di endpoint
    # (decode_logo) supaya file rusak ditolak 422 SEBELUM ada kerja berbayar.
    logo_base64: Optional[str] = None
