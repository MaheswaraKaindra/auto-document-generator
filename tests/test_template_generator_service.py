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


def test_repeated_content_chapters_dedup_first_wins():
    """Beberapa bab yang cocok isi SAMA (template IEEE: Introduction/Background/
    Overview → app_description) TAK mengulang isinya — yang pertama menang, sisanya
    turun jadi placeholder. Cegah paragraf/diagram berulang di dokumen."""
    spec = _spec([
        (1, "Introduction"),
        (1, "Background"),
        (1, "Overview of the System"),
    ])
    plan = tg.propose_mapping(spec, "SDD")
    app_desc = [p for p in plan if p["binding"] == tg.APP_DESCRIPTION]
    assert len(app_desc) == 1                       # cuma SEKALI, bukan 3x
    assert app_desc[0]["text"] == "Introduction"    # yang pertama menang


def test_scalar_content_chapter_keeps_its_subtree():
    """Bab isi SKALAR (app_description) TAK menelan sub-pohonnya — anak yang punya
    pemetaan sendiri tetap muncul, struktur bab template dipertahankan. (Beda dari
    use_cases yang memang mengganti sub-strukturnya.) Pelajaran template IEEE
    bersarang: dulu _OWNS_SUBTREE terlalu luas → 'Overview of Business Process'
    di bawah 'Background' ikut hilang."""
    spec = _spec([
        (1, "Background"),                       # → app_description (skalar)
        (2, "Overview of Business Process"),     # → business_flow, JANGAN hilang
        (2, "Scope"),                            # → manual, struktur tetap ada
    ])
    tmpl = tg.generate_jinja_template(tg.propose_mapping(spec, "SDD"))
    assert "{{ business_flow_description }}" in tmpl   # anak business_flow tetap dirender
    assert "# Scope" in tmpl                           # struktur template dipertahankan


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
    assert "![Use Case Diagram](img/uc.png)" in rendered   # SATU diagram gabungan
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


def test_orientation_marker_emitted_only_on_change():
    """Marker orientasi dipancarkan saat BERUBAH saja — bukan di tiap bab.
    Marker di tiap bab akan memecah dokumen jadi puluhan section tak berguna."""
    mapping = [
        {"level": 1, "text": "Pendahuluan", "binding": tg.MANUAL, "orient": "portrait"},
        {"level": 1, "text": "Ruang Lingkup", "binding": tg.MANUAL, "orient": "portrait"},
        {"level": 1, "text": "Matriks", "binding": tg.MANUAL, "orient": "landscape"},
        {"level": 1, "text": "Lampiran", "binding": tg.MANUAL, "orient": "landscape"},
        {"level": 1, "text": "Penutup", "binding": tg.MANUAL, "orient": "portrait"},
    ]

    template = tg.generate_jinja_template(mapping)

    assert template.count("((LANDSCAPE))") == 1
    assert template.count("((PORTRAIT))") == 1
    # Urutannya harus membungkus bab landscape, bukan sekadar ada.
    assert (template.index("((LANDSCAPE))") < template.index("# Matriks")
            < template.index("((PORTRAIT))") < template.index("# Penutup"))


def test_all_portrait_template_emits_no_marker():
    """Mayoritas template potret seluruhnya — jangan menambah section break
    (dan risiko regresi) pada dokumen yang tidak membutuhkannya."""
    mapping = [
        {"level": 1, "text": "Pendahuluan", "binding": tg.MANUAL, "orient": "portrait"},
        {"level": 1, "text": "Penutup", "binding": tg.MANUAL},  # tanpa orient sama sekali
    ]

    template = tg.generate_jinja_template(mapping)

    assert "((LANDSCAPE))" not in template
    assert "((PORTRAIT))" not in template


def test_mapping_health_berteriak_saat_peta_hampir_kosong():
    """Kegagalan senyap lebih mahal daripada kegagalan berisik.

    Kasus nyata: sebuah template vendor terkompilasi mulus, mengembalikan 201,
    lalu menghasilkan dokumen 20 halaman yang hampir seluruhnya placeholder —
    tanpa satu pun sinyal bahwa ada yang tidak beres. Pengguna baru tahu setelah
    membaca dokumen jadi, dan saat itu dia sudah membayar LLM."""
    from app.services.template_generator_service import mapping_health

    plan = [{"level": 0, "text": "Judul", "binding": "skip"},
            {"level": 1, "text": "Prospect", "binding": "manual"},
            {"level": 1, "text": "Pool", "binding": "manual"},
            {"level": 1, "text": "Solution Architecture", "binding": "architecture"}]

    health = mapping_health(plan)

    assert health["n_headings"] == 3          # bab `skip` tak ikut dihitung
    assert health["n_filled"] == 1
    assert health["unmapped"] == ["Prospect", "Pool"]
    assert "warning" in health


def test_mapping_health_diam_saat_peta_sehat():
    """Peringatan yang selalu menyala sama tak bergunanya dengan yang tak pernah."""
    from app.services.template_generator_service import mapping_health

    plan = [{"level": 1, "text": f"Bab {i}", "binding": b} for i, b in enumerate(
        ["app_description", "user_roles", "system_requirements",
         "feature_requirements", "use_cases", "architecture", "manual"])]

    health = mapping_health(plan)

    assert health["n_content_kinds"] == 6
    assert "warning" not in health


def test_mapping_health_tidak_menghukum_template_uat_yang_sehat():
    """Template UAT nyata mengikat 1 bab dari 24 — dan itu SEHAT.

    Yang satu itu tabel test case, isi utama sebuah dokumen UAT; sisanya
    (persetujuan, ruang lingkup, log defect) memang pekerjaan manusia. Ambang
    yang menghitung angka MUTLAK memvonis setiap template UAT sakit, sebab
    kosakata UAT cuma punya 2 jenis isi sementara SDD punya 8 — mustahil
    dipenuhi, dan peringatan yang selalu menyala akan diabaikan orang."""
    from app.services.template_generator_service import mapping_health

    plan = [{"level": 1, "text": "Persetujuan", "binding": "manual"},
            {"level": 1, "text": "Ruang Lingkup", "binding": "manual"},
            {"level": 1, "text": "Detail Testing", "binding": "test_groups"},
            {"level": 1, "text": "Log Defect", "binding": "manual"}]

    health = mapping_health(plan, "UAT")

    assert health["n_content_kinds_possible"] == 2
    assert health["filled_ratio"] == 0.25      # rendah, tapi bukan penanda sakit
    assert "warning" not in health
    # Peta SDD dengan isi sepersis itu justru SAKIT: 1 dari 8 jenis isi.
    assert "warning" in mapping_health(plan, "SDD")
