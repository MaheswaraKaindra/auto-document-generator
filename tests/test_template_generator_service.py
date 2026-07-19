"""Tes generator template (V2 increment 3, inti deterministik). Outline sintetis
+ fixture Contract B nyata (dummy_data) — tanpa LLM, tanpa docx vendor.

Yang paling dijaga: template HASIL-GENERATE benar-benar render di env Jinja
compiler (trim_blocks/lstrip_blocks) dengan Contract B nyata — markup valid, nol
`{{`/`{%` tersisa, isi berjejak. Sisanya: pemetaan kata kunci, degradasi anggun
(bab asing → placeholder jujur), dan pembuangan anak bab yang isinya diganti.
"""
import json
from pathlib import Path

from app.services import template_generator_service as tg
from app.services.compiler_service import _jinja_env

_DUMMY = Path(__file__).resolve().parent.parent / "dummy_data"


def _spec(rows):
    """`rows` = list (level, text) → TemplateSpec minimal (cukup untuk generator)."""
    return {"structure": {"outline": [{"level": lv, "text": tx, "empty": not tx}
                                      for lv, tx in rows]}}


def _bindings(plan):
    return {item["text"]: item["binding"] for item in plan}


def test_propose_mapping_classifies_sdd_chapters_by_keyword():
    spec = _spec([
        (0, "Solution Design Document"),      # judul → skip
        (1, "Daftar Isi"),                    # → skip
        (1, "1. Deskripsi Aplikasi"),         # → app_description
        (1, "2. System Requirement"),         # → system_requirements (bukan feature)
        (1, "3. Application Features"),        # → feature_requirements
        (1, "4. Application Architecture"),   # → architecture
        (1, "5. Use Case"),                   # → use_cases
        (1, "6. Activity Diagram"),           # → activity_diagrams
        (1, "7. Anggaran Biaya"),             # tak dikenali, daun → manual
    ])
    b = _bindings(tg.propose_mapping(spec, "SDD"))
    assert b["Solution Design Document"] == tg.SKIP
    assert b["Daftar Isi"] == tg.SKIP
    assert b["1. Deskripsi Aplikasi"] == tg.APP_DESCRIPTION
    assert b["2. System Requirement"] == tg.SYSTEM_REQUIREMENTS
    assert b["3. Application Features"] == tg.FEATURE_REQUIREMENTS
    assert b["4. Application Architecture"] == tg.ARCHITECTURE
    assert b["5. Use Case"] == tg.USE_CASES
    assert b["6. Activity Diagram"] == tg.ACTIVITY_DIAGRAMS
    assert b["7. Anggaran Biaya"] == tg.MANUAL


def test_propose_mapping_uat_test_chapter_and_container():
    spec = _spec([
        (1, "Pendahuluan"),          # tak dikenali, daun → manual (konservatif)
        (1, "Ringkasan Aplikasi"),   # → app_description
        (1, "Prosedur Testing"),     # kontainer (punya anak) → heading_only
        (2, "Test Objective"),       # anak, tak dikenali, daun → manual
        (1, "Detail Testing"),       # → test_groups
        (2, "Halaman Login"),        # anak dari test_groups (dibuang saat generate)
    ])
    b = _bindings(tg.propose_mapping(spec, "UAT"))
    assert b["Pendahuluan"] == tg.MANUAL              # heuristik konservatif, tak menebak
    assert b["Ringkasan Aplikasi"] == tg.APP_DESCRIPTION
    assert b["Prosedur Testing"] == tg.HEADING_ONLY   # kontainer, bukan test
    assert b["Test Objective"] == tg.MANUAL
    assert b["Detail Testing"] == tg.TEST_GROUPS


def test_unrecognized_chapter_degrades_to_honest_placeholder():
    """Bab asing yang tak ada di kode (mis. IEEE 'Data Design') → placeholder
    jujur, BUKAN karangan. Ini inti 'degradasi anggun'."""
    spec = _spec([(1, "Data Design"), (1, "Detailed Design")])
    tmpl = tg.generate_jinja_template(tg.propose_mapping(spec, "SDD"))
    assert "# Data Design" in tmpl
    assert "*(diisi manual)*" in tmpl
    # tak ada isi turunan-kode yang dikarang untuk bab yang tak dipetakan
    assert "{% for" not in tmpl.split("# Detailed Design")[0].split("# Data Design")[1]


def test_generate_drops_children_of_content_bound_chapter():
    """Anak bab yang isinya diganti turunan-kode (use case) DIBUANG — sampel
    sub-bab template di-upload digantikan loop Contract B."""
    spec = _spec([
        (1, "Use Case"),
        (2, "Contoh Use Case Login"),   # sampel di template upload → harus hilang
        (2, "Contoh Use Case Logout"),
        (1, "Penutup"),                 # sejajar → muncul lagi
    ])
    tmpl = tg.generate_jinja_template(tg.propose_mapping(spec, "SDD"))
    assert "# Use Case" in tmpl
    assert "Contoh Use Case Login" not in tmpl
    assert "{% for uc in use_cases %}" in tmpl
    assert "# Penutup" in tmpl            # bab sejajar sesudahnya tetap ada


def test_generated_sdd_template_renders_with_real_contract_b():
    """Smoke terpenting: template hasil-generate render di env Jinja compiler
    dengan Contract B nyata — markup valid, nol tag Jinja tersisa, isi berjejak."""
    data = json.loads((_DUMMY / "document_content_sdd.json").read_text(encoding="utf-8"))
    spec = _spec([
        (1, "Deskripsi Aplikasi"),
        (1, "System Requirement"),
        (1, "Application Features"),
        (1, "Use Case"),
        (1, "Activity Diagram"),
        (1, "Lampiran Mockup"),      # → manual
    ])
    tmpl = tg.generate_jinja_template(tg.propose_mapping(spec, "SDD"))

    # Konteks minimal: list Contract B nyata + diagram dummy (tanpa render PlantUML).
    dummy_attr = "{ width=6in }"
    diagrams = {
        "system_architecture_image": "img/a.png", "system_architecture_attr": dummy_attr,
        "use_case_diagram_image": "img/uc.png", "use_case_diagram_attr": dummy_attr,
        "business_process_flow_image": "img/bf.png", "business_process_flow_attr": dummy_attr,
        "activity_diagrams": [
            {**a, "image_path": "img/act.png", "image_attr": dummy_attr}
            for a in data["diagrams"]["activity_diagrams"]
        ],
    }
    context = {**data, "project_name": "Proyek Contoh", "meta": {}, "diagrams": diagrams}

    rendered = _jinja_env.from_string(tmpl).render(**context)

    assert "{{" not in rendered and "{%" not in rendered   # semua tag terpakai
    assert "*(diisi manual)*" in rendered                  # bab Mockup jadi placeholder
    # isi berjejak ke fixture
    assert data["feature_requirements"][0]["feature_name"] in rendered
    assert data["use_cases"][0]["use_case_id"] in rendered
    assert "ACT001" in rendered                            # penomoran activity deterministik


def test_generated_uat_template_renders_grouped_test_cases():
    """Template UAT hasil-generate mengelompokkan test-case per modul & render."""
    spec = _spec([(1, "Pendahuluan"), (1, "Detail Testing")])
    tmpl = tg.generate_jinja_template(tg.propose_mapping(spec, "UAT"))

    groups = [
        {"group_name": "Halaman Login", "test_cases": [
            {"role": "Admin", "activity": "Login sah",
             "steps": "Isi kredensial", "expected_result": "Masuk dashboard"}]},
        {"group_name": "Halaman Produk", "test_cases": [
            {"role": "Admin", "activity": "Tambah produk",
             "steps": "Isi form", "expected_result": "Produk tersimpan"}]},
    ]
    context = {"uat_test_groups": groups, "project_name": "Proyek Contoh", "meta": {},
               "app_description": "Deskripsi aplikasi contoh."}
    rendered = _jinja_env.from_string(tmpl).render(**context)

    assert "{{" not in rendered and "{%" not in rendered
    assert "Case Pengujian: Halaman Login" in rendered
    assert "Case Pengujian: Halaman Produk" in rendered
    assert "Masuk dashboard" in rendered
