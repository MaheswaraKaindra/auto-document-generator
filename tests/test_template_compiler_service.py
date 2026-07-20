"""Tes kompilasi template upload jadi template terdaftar (V2 — pendaftaran +
storage). Spec sintetis + Contract B nyata (dummy_data), plantuml di-mock.

Yang dijaga: compile_template menulis artefak lengkap + terdaftar, DAN
generate_docx dengan template_id hasil-kompilasi benar-benar merender docx lewat
reference.docx TERSINTESIS-nya sendiri (bukan PREMCO ter-commit).
"""
import io
import json
import zipfile
from pathlib import Path

import pytest
from docx import Document
from PIL import Image

from app.services import compiler_service, template_compiler_service

_DUMMY = Path(__file__).resolve().parent.parent / "dummy_data"


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (12, 12), (240, 240, 240)).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """Redirect store template + folder output ke tmp, dan mock proses plantuml —
    supaya test tak menulis ke data/ asli, tak butuh Java, tak butuh jaringan."""
    monkeypatch.setattr(compiler_service, "TEMPLATES_STORE", tmp_path / "templates")
    monkeypatch.setattr(compiler_service, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(compiler_service, "IMAGES_DIR", tmp_path / "out" / "images")
    monkeypatch.setattr(compiler_service, "_run_plantuml", lambda *a, **k: _png_bytes())
    return tmp_path


def _spec():
    return {
        "doc_kind_guess": "SDD",
        "visual": {
            "effective_heading_font": "Tahoma",
            "effective_body_font": "Verdana",
            "title": {"size_pt": 18, "bold": True, "caps": False, "align": "left"},
            "headings": {"Heading 1": {"size_pt": 14, "bold": True, "caps": False,
                                       "align": "left"}},
            "table_header_fill": "A4A4A4",
        },
        "structure": {"outline": [
            {"level": 0, "text": "Solution Design Document"},
            {"level": 1, "text": "1. Deskripsi Aplikasi"},
            {"level": 1, "text": "2. System Requirement"},
            {"level": 1, "text": "3. Application Features Requirement"},
            {"level": 1, "text": "4. Use Case"},
            {"level": 1, "text": "5. Lampiran Mockup"},
        ]},
    }


def test_compile_template_writes_registered_artifacts(isolated_store):
    manifest = template_compiler_service.compile_template(_spec(), "ACME SDD Template")
    tid = manifest["template_id"]
    base = compiler_service.TEMPLATES_STORE / tid

    assert tid == "acme-sdd-template"                 # slug dari nama
    for f in ("template.json", "SDD.md", "reference.docx", "spec.json", "mapping_SDD.json"):
        assert (base / f).exists(), f
    assert manifest["doc_types"] == {"SDD": "SDD.md"}
    assert manifest["reference"] == "reference.docx"
    assert manifest["groups_test_cases"] is True
    assert manifest["uses_component_integration"] is False
    assert manifest["splits_usecase"] is True             # use case per-aktor untuk template upload

    # terdaftar + validasi (jalur 422 sinkron endpoint)
    assert tid in compiler_service.list_template_ids()
    compiler_service.validate_template(tid, "SDD")     # tak melempar
    with pytest.raises(ValueError, match="belum menyediakan"):
        compiler_service.validate_template(tid, "UAT")  # spec ini SDD-saja


def test_generate_docx_renders_compiled_template_with_its_own_reference(isolated_store):
    manifest = template_compiler_service.compile_template(_spec(), "ACME SDD")
    tid = manifest["template_id"]
    data = json.loads((_DUMMY / "document_content_sdd.json").read_text(encoding="utf-8"))

    out = compiler_service.generate_docx("SDD", data, project_name="Proyek Uji",
                                         template_id=tid)

    assert Path(out).exists()
    doc = Document(out)
    text = "\n".join(p.text for p in doc.paragraphs)
    assert data["app_description"] in text                 # isi Contract B nyata
    assert "Deskripsi Aplikasi" in text                    # bab dari outline template
    # "*(diisi manual)*" jadi teks MIRING di docx — asterisk penanda italic dibuang
    assert "(diisi manual)" in text                        # "Lampiran Mockup" → placeholder

    # DIRENDER lewat reference.docx TERSINTESIS (Tahoma/Verdana), bukan PREMCO
    # ter-commit (Calibri) — bukti jalur reference per-template bekerja.
    with zipfile.ZipFile(out) as z:
        theme = z.read("word/theme/theme1.xml").decode("utf-8")
    import re
    assert re.findall(r'<a:latin typeface="([^"]*)"', theme) == ["Tahoma", "Verdana"]


def test_compile_is_idempotent_on_id_but_unique_per_call(isolated_store):
    """Dua kompilasi dengan nama sama tidak saling menimpa — id kedua di-suffix."""
    a = template_compiler_service.compile_template(_spec(), "Sama")["template_id"]
    b = template_compiler_service.compile_template(_spec(), "Sama")["template_id"]
    assert a == "sama"
    assert b == "sama-2"
    assert a in compiler_service.list_template_ids()
    assert b in compiler_service.list_template_ids()


def test_compile_from_docx_measures_then_registers(isolated_store, tmp_path):
    """Jalur lengkap dari .docx: build_template_spec → compile_template."""
    doc = Document()
    doc.add_paragraph("Judul", style="Title")
    doc.add_paragraph("Deskripsi Aplikasi", style="Heading 1")
    doc.add_paragraph("Use Case", style="Heading 1")
    src = tmp_path / "vendor_sdd.docx"
    doc.save(str(src))

    manifest = template_compiler_service.compile_template_from_docx(src, doc_types=["SDD"])
    tid = manifest["template_id"]
    assert (compiler_service.TEMPLATES_STORE / tid / "SDD.md").exists()
    template_md = (compiler_service.TEMPLATES_STORE / tid / "SDD.md").read_text(encoding="utf-8")
    assert "{{ app_description }}" in template_md          # "Deskripsi Aplikasi" ter-bind
    assert "{% for uc in use_cases %}" in template_md      # "Use Case" ter-bind


def test_use_llm_mapping_opt_in_calls_llm_mapper(isolated_store, monkeypatch):
    """use_llm_mapping=True memakai pemeta LLM (di-mock di boundary orkestrator)."""
    calls = []

    def fake_llm(spec, dt):
        calls.append(dt)
        return [{"level": 1, "text": "Deskripsi", "binding": "app_description"}]

    monkeypatch.setattr(template_compiler_service, "llm_propose_mapping", fake_llm)
    manifest = template_compiler_service.compile_template(
        _spec(), "LLM Opt In", use_llm_mapping=True)
    assert calls == ["SDD"]                              # dipanggil utk doc_type SDD
    tid = manifest["template_id"]
    md = (compiler_service.TEMPLATES_STORE / tid / "SDD.md").read_text(encoding="utf-8")
    assert "{{ app_description }}" in md                 # rencana LLM ter-render


def test_default_path_does_not_call_llm_mapper(isolated_store, monkeypatch):
    """Default (use_llm_mapping=False) TIDAK menyentuh LLM — jalur $0 tetap heuristik."""
    def boom(spec, dt):
        raise AssertionError("pemeta LLM tak boleh dipanggil pada jalur default")

    monkeypatch.setattr(template_compiler_service, "llm_propose_mapping", boom)
    template_compiler_service.compile_template(_spec(), "Default Heuristik")
    # sampai sini tanpa AssertionError = LLM tak dipanggil
