"""Tes pemeta bab BER-LLM (V2, #2 produksionisasi). LLM di-mock — monkeypatch
`_request_bindings` (satu-satunya titik jaringan), jadi $0 & tanpa kunci API.

Yang dijaga: kontrak keluaran SAMA dgn propose_mapping, dedup + degradasi anggun
(lewat assemble_plan bersama), filter binding-isi per doc_type, dan enum binding
tak menyimpang dari konstanta.
"""
from typing import get_args

from app.services import llm_mapping_service as lm
from app.services.template_generator_service import (
    HEADING_ONLY,
    MANUAL,
    SKIP,
    _CONTENT_BINDINGS,
)


def _spec(outline):
    return {"structure": {"outline": outline}}


def _mock_llm(monkeypatch, raw: dict):
    monkeypatch.setattr(lm, "_request_bindings",
                        lambda outline, doc_type, usage_sink=None: raw)


def test_binding_literal_matches_vocabulary():
    # _Binding (enum structured-output) tak boleh menyimpang dari konstanta binding
    assert set(get_args(lm._Binding)) == {SKIP, HEADING_ONLY, MANUAL} | _CONTENT_BINDINGS


def test_maps_foreign_chapters_that_heuristic_misses(monkeypatch):
    # Skenario Dynamics: bab asing (kata kunci tak cocok) TETAP terpetakan lewat LLM
    outline = [
        {"level": 0, "text": "Solution Design Document"},
        {"level": 2, "text": "Vision Statement"},
        {"level": 2, "text": "Business Capabilities"},
        {"level": 2, "text": "Setup"},
    ]
    _mock_llm(monkeypatch, {0: "skip", 1: "app_description",
                            2: "feature_requirements", 3: "manual"})
    plan = lm.llm_propose_mapping(_spec(outline), "SDD")
    assert [p["binding"] for p in plan] == \
        ["skip", "app_description", "feature_requirements", "manual"]
    # kontrak keluaran: paralel outline, level+text+orient terbawa. `orient` itu
    # fakta TATA LETAK hasil pengukuran, bukan keputusan pemetaan — jadi jalur
    # LLM pun cuma meneruskannya (default potret kalau outline tak membawanya).
    assert plan[1] == {"level": 2, "text": "Vision Statement",
                       "binding": "app_description", "orient": "portrait"}


def test_title_and_empty_always_skip(monkeypatch):
    # Struktural: level 0 & teks kosong -> SKIP, apa pun jawaban LLM
    outline = [{"level": 0, "text": "Judul"}, {"level": 2, "text": ""}]
    _mock_llm(monkeypatch, {0: "app_description", 1: "feature_requirements"})
    plan = lm.llm_propose_mapping(_spec(outline), "SDD")
    assert [p["binding"] for p in plan] == ["skip", "skip"]


def test_dedup_safety_when_llm_repeats_content_binding(monkeypatch):
    # LLM langgar "sekali per binding" -> yang kedua didemote (first-wins)
    outline = [{"level": 1, "text": "Overview"}, {"level": 1, "text": "Introduction"}]
    _mock_llm(monkeypatch, {0: "app_description", 1: "app_description"})
    plan = lm.llm_propose_mapping(_spec(outline), "SDD")
    assert plan[0]["binding"] == "app_description"
    assert plan[1]["binding"] == "manual"        # daun -> manual


def test_doc_type_filter_drops_test_groups_in_sdd(monkeypatch):
    # test_groups bukan konten SDD -> dibuang jadi fallback (koherensi dokumen)
    outline = [{"level": 1, "text": "Detail Testing"}]
    _mock_llm(monkeypatch, {0: "test_groups"})
    plan = lm.llm_propose_mapping(_spec(outline), "SDD")
    assert plan[0]["binding"] == "manual"


def test_doc_type_filter_drops_use_cases_in_uat(monkeypatch):
    outline = [{"level": 1, "text": "Skenario"}]
    _mock_llm(monkeypatch, {0: "use_cases"})
    plan = lm.llm_propose_mapping(_spec(outline), "UAT")
    assert plan[0]["binding"] == "manual"


def test_test_groups_allowed_in_uat(monkeypatch):
    outline = [{"level": 1, "text": "Detail Testing"}]
    _mock_llm(monkeypatch, {0: "test_groups"})
    plan = lm.llm_propose_mapping(_spec(outline), "UAT")
    assert plan[0]["binding"] == "test_groups"


def test_missing_chapter_falls_back_by_children(monkeypatch):
    # Bab yang LLM lewatkan (tak ada di raw): kontainer -> heading_only, daun -> manual
    outline = [{"level": 1, "text": "Data Master Design"}, {"level": 2, "text": "Prospect"}]
    _mock_llm(monkeypatch, {})   # LLM tak menjawab satu pun
    plan = lm.llm_propose_mapping(_spec(outline), "SDD")
    assert plan[0]["binding"] == "heading_only"   # punya anak (level 2 di bawahnya)
    assert plan[1]["binding"] == "manual"         # daun
