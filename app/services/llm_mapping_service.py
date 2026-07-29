"""V2 — pemeta bab BER-LLM (alternatif ber-judgment untuk propose_mapping heuristik).

Kontrak keluaran SAMA dengan `template_generator_service.propose_mapping`:
`[{level, text, binding}, ...]` — jadi bisa dipertukarkan. Bedanya: binding per
bab diputuskan Claude, bukan kata kunci. Jadi bab asing yang kata kuncinya tak
cocok TETAP terpetakan bila ada padanan semantik ("Vision Statement" →
app_description, "Business Capabilities" → feature_requirements). Pada template
SDD non-PREMCO nyata (Microsoft Dynamics), heuristik menghasilkan 0 binding isi
(dokumen 100% placeholder) sementara LLM 4 binding isi — lihat Riwayat CLAUDE.md
2026-07-20.

BERBAYAR & OPT-IN. Satu panggilan Claude per (template × doc_type), terjadi SEKALI
saat template dikompilasi (bukan tiap generate dokumen). Jalur default tetap
heuristik $0 — gate `use_llm_mapping` ada di `template_compiler_service`.

Logika STRUKTURAL (dedup isi, degradasi anggun, SKIP judul/kosong) TIDAK diulang
di sini: dipakai bersama lewat `template_generator_service.assemble_plan`. Modul
ini cuma menyediakan `classify` per bab (jawaban LLM) + safety filter doc_type.
"""
from __future__ import annotations

import logging
from typing import List, Literal

import anthropic
from pydantic import BaseModel, Field

from app.core import config
from app.services.template_generator_service import (
    ACTIVITY_DIAGRAMS,
    APP_DESCRIPTION,
    ARCHITECTURE,
    BUSINESS_FLOW,
    FEATURE_REQUIREMENTS,
    SYSTEM_REQUIREMENTS,
    TEST_GROUPS,
    USE_CASES,
    USER_ROLES,
    _CONTENT_BINDINGS,
    assemble_plan,
)

logger = logging.getLogger(__name__)

_TIMEOUT = 300.0          # peta bab kecil; jauh di bawah timeout generate dokumen
_MAX_TOKENS = 8000        # ruang untuk thinking + daftar binding puluhan bab

# Kosakata isi yang RELEVAN per jenis dokumen — cermin target aturan heuristik
# (_SDD_RULES / _UAT_RULES). Binding isi di luar set ini untuk doc_type tsb.
# dibuang jadi None (→ fallback jujur) supaya dokumen tetap koheren: LLM tak boleh
# menaruh tabel test-case di SDD, atau diagram arsitektur di UAT.
_SDD_CONTENT = {
    APP_DESCRIPTION, USER_ROLES, SYSTEM_REQUIREMENTS, FEATURE_REQUIREMENTS,
    USE_CASES, ACTIVITY_DIAGRAMS, ARCHITECTURE, BUSINESS_FLOW,
}
_UAT_CONTENT = {APP_DESCRIPTION, TEST_GROUPS}

# Enum binding untuk structured output — seluruh kosakata (struktural + isi);
# post-filter per doc_type dilakukan di `classify`. Test menjaga daftar ini tidak
# menyimpang dari konstanta di template_generator_service.
_Binding = Literal[
    "skip", "heading_only", "manual",
    "app_description", "user_roles", "system_requirements", "feature_requirements",
    "use_cases", "activity_diagrams", "architecture", "business_flow", "test_groups",
]


class _ChapterBinding(BaseModel):
    index: int = Field(description="Index bab (0-based) dari daftar outline yang diberikan.")
    text: str = Field(description="Teks judul bab disalin apa adanya (verifikasi keselarasan).")
    binding: _Binding = Field(description="Binding terpilih untuk bab ini.")


class _TemplateMapping(BaseModel):
    strategy: str = Field(description="Ringkasan 1-2 kalimat strategi pemetaan (Bahasa Indonesia).")
    chapters: List[_ChapterBinding]


def _system_prompt(doc_type: str) -> str:
    if doc_type == "UAT":
        content_desc = (
            "- app_description : ringkasan/pengantar aplikasi yang diuji\n"
            "- test_groups     : bab yang memuat kasus/skenario/skrip pengujian "
            "(mis. 'Detail Testing', 'Test Script', 'Case Pengujian')"
        )
    else:
        content_desc = (
            "- app_description      : ringkasan/visi/latar belakang aplikasi "
            "(mis. 'Vision Statement', 'Overview', 'Introduction', 'Background')\n"
            "- user_roles           : daftar peran/aktor pengguna\n"
            "- system_requirements  : teknologi/stack/kebutuhan sistem\n"
            "- feature_requirements : daftar fitur/kapabilitas fungsional "
            "(mis. 'Business Capabilities', 'Functional Requirements')\n"
            "- use_cases            : use case per aktor\n"
            "- activity_diagrams    : diagram/alur aktivitas per fitur\n"
            "- architecture         : arsitektur sistem/aplikasi/desain teknis high-level\n"
            "- business_flow        : alur proses bisnis end-to-end"
        )
    return f"""Anda memetakan bab-bab TEMPLATE dokumen {doc_type} yang di-upload user ke
"binding" konten yang bisa diisi otomatis dari analisis kode. Untuk TIAP bab, pilih
SATU binding.

BINDING KONTEN (turunan-kode; tiap binding dipakai PALING BANYAK SEKALI di seluruh
dokumen — pilih bab yang PALING pas untuk masing-masing):
{content_desc}

BINDING STRUKTURAL:
- skip         : judul dokumen, Daftar Isi/Gambar/Tabel (tidak diemisikan)
- heading_only : bab KONTAINER (punya sub-bab lebih dalam) yang isinya ada di anak-anaknya
- manual       : placeholder jujur — untuk bab yang TIDAK bisa diturunkan dari kode
                 (mis. Change Record, Client Review, Cost, Timeline, Setup, tanda tangan)

ATURAN:
1. Petakan dengan MURAH HATI di mana ada kecocokan semantik yang wajar — itu inti tugas
   ini, jangan terlalu konservatif. TAPI jangan mengada-ada: tanpa padanan kode yang
   masuk akal, pakai manual.
2. Tiap binding KONTEN paling banyak SEKALI. Kalau beberapa bab cocok ke binding sama,
   pilih SATU yang paling representatif; sisanya heading_only (punya anak) atau manual.
3. Bab kontainer yang isinya diwakili sub-bab → heading_only.
4. Salin `text` apa adanya dan pertahankan `index`."""


def _request_bindings(outline: list[dict], doc_type: str,
                      usage_sink: list | None = None) -> dict[int, str]:
    """Panggil Claude → `{index bab: binding}`. Ini SATU-SATUNYA titik jaringan
    berbayar modul ini — di-mock di test (monkeypatch fungsi ini).

    `usage_sink`: kalau diberi, pemakaian token panggilan ini di-append ke sana
    (bentuknya sama dengan `_usage` di llm_service, supaya `record_job_usage` bisa
    memakan keduanya tanpa cabang). Panggilan ini BERBAYAR persis seperti generate
    dokumen; tanpa kanal ini biayanya tak pernah sampai ke panel billing dan
    dashboard biaya melaporkan angka yang lebih kecil dari tagihan sesungguhnya.
    """
    lines = [
        f"[{i}] level={o.get('level')} | {(o.get('text') or '').strip()!r}"
        for i, o in enumerate(outline)
    ]
    user = "Outline template (index, level, judul):\n" + "\n".join(lines)

    client = anthropic.Anthropic(timeout=_TIMEOUT)
    with client.messages.stream(
        model=config.LLM_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_system_prompt(doc_type),
        messages=[{"role": "user", "content": user}],
        output_format=_TemplateMapping,
    ) as stream:
        response = stream.get_final_message()

    result = response.parsed_output
    usage = response.usage
    logger.info(
        "LLM peta bab %s: input=%s output=%s bab=%s | strategi=%s",
        doc_type, usage.input_tokens, usage.output_tokens,
        len(result.chapters), result.strategy,
    )
    if usage_sink is not None:
        usage_sink.append({
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
        })
    return {c.index: c.binding for c in result.chapters}


def llm_propose_mapping(spec: dict, doc_type: str,
                        usage_sink: list | None = None) -> list[dict]:
    """Peta bab BER-LLM. Kontrak keluaran SAMA dengan
    `template_generator_service.propose_mapping` (list `[{level, text, binding}]`),
    jadi bisa dipertukarkan. BERBAYAR — satu panggilan Claude.

    Buang binding isi yang tak relevan dengan `doc_type` (safety) lalu rakit lewat
    `assemble_plan` (dedup + degradasi anggun, seragam dengan heuristik).
    """
    outline = spec.get("structure", {}).get("outline", [])
    normalized = doc_type.upper()
    allowed = _UAT_CONTENT if normalized == "UAT" else _SDD_CONTENT
    raw = _request_bindings(outline, normalized, usage_sink)

    def classify(i: int, _entry: dict):
        binding = raw.get(i)
        if binding in _CONTENT_BINDINGS and binding not in allowed:
            return None    # binding isi tak relevan untuk doc_type → fallback jujur
        return binding

    return assemble_plan(outline, classify)
