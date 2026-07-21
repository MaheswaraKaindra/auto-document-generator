"""V2 increment 3 (inti deterministik) — generate template Jinja dari outline.

Bagian ketiga pipeline "upload template jadi template terdaftar" (roadmap tahap
c). Mengubah **outline** sebuah `TemplateSpec` (increment 1) menjadi **template
Jinja `.md`** yang, saat diisi Contract B lalu dirender lewat reference.docx
tersintesis (increment 2), menghasilkan dokumen bergaya template yang di-upload.

DUA LANGKAH, sengaja dipisah supaya bisa ditinjau manusia di antaranya:

  1. `propose_mapping(spec, doc_type)` → **rencana pemetaan**: untuk tiap bab di
     outline, satu "binding" (bab ini diisi apa). Deterministik, berbasis kata
     kunci — ini **stand-in untuk usulan LLM** yang datang kelak; bentuk
     keluarannya (list `{level, text, binding}`) memang dirancang untuk
     ditampilkan & diedit di UI tinjauan.
  2. `generate_jinja_template(mapping)` → **string template Jinja** mengikuti
     urutan bab. Bab yang punya isi turunan-kode di-bind ke loop/tabel Contract
     B; bab yang tak ada di kode → **placeholder jujur** `*(diisi manual)*`
     (degradasi anggun — setia nilai jual: "30 halaman benar > 87 halaman
     separuh karangan").

Snippet Jinja-nya DIAMBIL dari template `default` yang sudah terbukti render
(tabel role/requirement/feature/use-case/activity, tabel test-case) — bukan
ditulis baru — supaya markup-nya pasti valid di bawah `trim_blocks`/`lstrip_blocks`
compiler. Warna header tabel TIDAK dipasang di sini (tanpa marker `((GH))` dsb.):
untuk template hasil-generate, warna datang dari `tblStylePr firstRow`
reference.docx tersintesis, yang sudah spec-driven (increment 2).

Kelayakan seluruh rantai (spec→peta→template→isi→render) sudah dibuktikan $0 pada
template non-PREMCO nyata — lihat `scripts/validation/V2_TEMPLATE_MULTISOURCE.md`.

BATAS yang DISENGAJA (checkpoint berikutnya, bukan lupa):
- Peta heuristik ini konservatif: bab yang namanya tak dikenali → `manual`
  (placeholder), bukan ditebak. LLM-lah yang kelak memetakan bab asing dengan
  judgment; modul ini menyediakan kontрак + jalur deterministik yang dia isi.
- Belum: pendaftaran ke `_TEMPLATE_REGISTRY` + penyimpanan artefak (butuh desain
  storage), orientasi landscape per-section, dan UI tinjauan.
"""
from __future__ import annotations

import re

# --- Kosakata binding ---------------------------------------------------------
# Struktural
SKIP = "skip"                    # judul / Daftar Isi — tak diemisikan
HEADING_ONLY = "heading_only"    # bab kontainer: cuma heading, anak yang mengisi
MANUAL = "manual"                # placeholder jujur *(diisi manual)*
# Isi turunan-kode (Contract B)
APP_DESCRIPTION = "app_description"
USER_ROLES = "user_roles"
SYSTEM_REQUIREMENTS = "system_requirements"
FEATURE_REQUIREMENTS = "feature_requirements"
USE_CASES = "use_cases"
ACTIVITY_DIAGRAMS = "activity_diagrams"
ARCHITECTURE = "architecture"
BUSINESS_FLOW = "business_flow"
TEST_GROUPS = "test_groups"      # tabel test-case dikelompokkan per modul/layar

# Semua binding turunan-kode (untuk dedup: satu bab sumber = satu isi; bab lain
# yang meminta isi SAMA jangan mengulanginya — lihat propose_mapping).
_CONTENT_BINDINGS = {
    APP_DESCRIPTION, USER_ROLES, SYSTEM_REQUIREMENTS, FEATURE_REQUIREMENTS,
    USE_CASES, ACTIVITY_DIAGRAMS, ARCHITECTURE, BUSINESS_FLOW, TEST_GROUPS,
}

# Binding yang meng-emit SUB-HEADING sendiri (loop `### ...`) → anak bab yang
# di-upload di bawahnya DIBUANG, digantikan isi turunan-kode (mis. sampel "Contoh
# Use Case Login" diganti loop use_cases). HANYA yang benar-benar menghasilkan
# sub-struktur — BUKAN isi skalar (app_description/architecture/dst.). Pelajaran
# dari template IEEE nyata (bersarang dalam): kalau isi skalar ikut menelan
# sub-pohon, bab anak yang punya pemetaan sendiri (mis. "Overview of Business
# Process"→business_flow di bawah "Background"→app_description) ikut HILANG, dan
# struktur bab template (Scope, Purpose, ...) yang seharusnya jadi placeholder
# ikut terbuang. Uji sintetis (outline datar) tak pernah memunculkan ini.
_OWNS_SUBTREE = {USE_CASES, ACTIVITY_DIAGRAMS, TEST_GROUPS}

# --- Aturan kata kunci bab → binding (dicek berurutan, cocok pertama menang) ---
# Frasa spesifik didahulukan sebelum yang umum (mis. "system requirement" sebelum
# "requirement"; frasa test-case spesifik sebelum kata "testing" yang terlalu luas
# — "Prosedur Testing" itu boilerplat, bukan tabel test-case).
_SDD_RULES: list[tuple[tuple[str, ...], str]] = [
    (("use case", "use-case", "usecase"), USE_CASES),
    (("activity diagram", "diagram aktivitas", "diagram aktifitas", "activity"), ACTIVITY_DIAGRAMS),
    (("system architecture", "arsitektur sistem", "application architecture",
      "arsitektur aplikasi", "architecture", "arsitektur"), ARCHITECTURE),
    (("flow proses bisnis", "business process flow", "proses bisnis",
      "business process", "alur proses"), BUSINESS_FLOW),
    (("system requirement", "kebutuhan sistem", "spesifikasi sistem",
      "system requirements"), SYSTEM_REQUIREMENTS),
    (("feature", "fitur", "functional requirement", "kebutuhan fungsional"), FEATURE_REQUIREMENTS),
    (("user role", "peran pengguna", "pengguna dan peran", "role", "aktor"), USER_ROLES),
    (("deskripsi aplikasi", "application description", "ringkasan aplikasi",
      "deskripsi sistem", "gambaran umum", "overview", "latar belakang",
      "background", "pendahuluan", "introduction"), APP_DESCRIPTION),
]
_UAT_RULES: list[tuple[tuple[str, ...], str]] = [
    (("detail testing", "case pengujian", "skenario pengujian", "test case",
      "test script", "hasil pengujian", "pelaksanaan pengujian",
      "kasus pengujian"), TEST_GROUPS),
    (("ringkasan aplikasi", "deskripsi aplikasi", "application description",
      "gambaran umum"), APP_DESCRIPTION),
]
_SKIP_KEYWORDS = ("daftar isi", "table of contents", "daftar gambar", "daftar tabel")


def _norm(text: str) -> str:
    """Kunci pencocokan: huruf kecil, tanpa penomoran depan ("1. ", "2) "),
    spasi rapat. Teks heading ASLI tetap dipakai untuk tampilan."""
    text = re.sub(r"^\s*\d+([.)]\d+)*[.)]?\s*", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _classify(key: str, rules) -> str | None:
    for keywords, binding in rules:
        if any(kw in key for kw in keywords):
            return binding
    return None


def assemble_plan(outline: list[dict], classify) -> list[dict]:
    """Rangkai rencana peta dari `outline` + `classify(i, entry) -> binding | None`.

    Menyatukan logika STRUKTURAL yang dipakai bersama pemeta heuristik
    (`propose_mapping`) dan pemeta LLM (`llm_mapping_service.llm_propose_mapping`)
    — satu sumber kebenaran supaya keduanya tak menyimpang diam-diam:
    - judul dokumen / bab kosong (`level == 0` atau teks kosong) → SKIP;
    - DEDUP isi turunan-kode: tiap binding di `_CONTENT_BINDINGS` dipakai PALING
      BANYAK SEKALI (yang pertama menang); bab kedua yang meminta isi sama (mis.
      template IEEE punya "Introduction"/"Background"/"Overview" — semua cocok
      app_description) turun jadi kontainer/placeholder, supaya paragraf/diagram
      yang sama tidak berulang;
    - bab tak-terpetakan (`classify` → None): **kontainer** (punya anak lebih
      dalam) → `heading_only`, **daun** → `manual` (placeholder jujur, bukan karangan).

    `classify` HANYA memutuskan binding usulan per bab; degradasi anggun & dedup
    seragam di sini.
    """
    plan = []
    used_content: set[str] = set()
    for i, entry in enumerate(outline):
        level = entry.get("level", 1)
        text = (entry.get("text") or "").strip()
        if not text or level == 0:            # judul dokumen: ditangani pandoc
            plan.append({"level": level, "text": text, "binding": SKIP})
            continue
        has_children = (i + 1 < len(outline)
                        and outline[i + 1].get("level", 1) > level)
        binding = classify(i, entry)
        if binding in _CONTENT_BINDINGS and binding in used_content:
            binding = None                    # isi ini sudah dipakai bab lain
        if binding is None:                   # tak dikenali / sudah dipakai
            binding = HEADING_ONLY if has_children else MANUAL
        elif binding in _CONTENT_BINDINGS:
            used_content.add(binding)
        plan.append({"level": level, "text": text, "binding": binding})
    return plan


def propose_mapping(spec: dict, doc_type: str) -> list[dict]:
    """Usulkan binding untuk tiap entri outline `spec` — HEURISTIK, deterministik ($0).

    Mengembalikan list paralel outline: `[{level, text, binding}, ...]` — rencana
    lengkap (termasuk entri SKIP) untuk ditampilkan/diedit di UI tinjauan lalu
    diteruskan apa adanya ke `generate_jinja_template`. `doc_type` ("SDD"/"UAT")
    menentukan kosakata isi (bab test-case cuma untuk UAT; use case/activity untuk SDD).

    Pencocokan berbasis KATA KUNCI (`_classify`), sengaja konservatif: nama bab
    yang tak dikenali → placeholder, tidak menebak. Alternatif ber-judgment
    (memetakan bab asing yang kata kuncinya tak cocok — mis. "Vision Statement" →
    app_description) ada di `llm_mapping_service.llm_propose_mapping` (berbayar,
    opt-in); kontrak keluarannya SAMA, jadi bisa dipertukarkan.
    """
    outline = spec.get("structure", {}).get("outline", [])
    rules = _UAT_RULES if doc_type.upper() == "UAT" else _SDD_RULES

    def classify(_i, entry):
        key = _norm((entry.get("text") or "").strip())
        if any(kw in key for kw in _SKIP_KEYWORDS):
            return SKIP
        return _classify(key, rules)

    return assemble_plan(outline, classify)


# --- Badan Jinja per binding (diambil dari template default yang terbukti) -----
# Bukan f-string: berisi `{% %}`/`{{ }}` literal yang DIEMISIKAN, bukan dirender.
_BODY = {
    APP_DESCRIPTION: "{{ app_description }}",

    USER_ROLES: (
        "| No. | Nama Role | Keterangan |\n"
        "|:---:|-------------|--------------------------------|\n"
        "{% for role in user_roles -%}\n"
        "| {{ loop.index }} | {{ role.role_name }} | {{ role.description }} |\n"
        "{% endfor %}"
    ),

    SYSTEM_REQUIREMENTS: (
        "| No. | System Requirement | Uraian |\n"
        "|:---:|--------------------|--------------------------------|\n"
        "{% for requirement in system_requirements -%}\n"
        "| {{ loop.index }} | {{ requirement.name }} | {{ requirement.detail }} |\n"
        "{% endfor %}"
    ),

    FEATURE_REQUIREMENTS: (
        "| No. | Fitur Aplikasi | Deskripsi Fitur |\n"
        "|:---:|----------------|--------------------------------|\n"
        "{% for feature in feature_requirements -%}\n"
        "| {{ loop.index }} | {{ feature.feature_name }} | {{ feature.description }} |\n"
        "{% endfor %}"
    ),

    ARCHITECTURE: (
        "![Arsitektur Sistem]({{ diagrams.system_architecture_image }})"
        "{{ diagrams.system_architecture_attr }}"
    ),

    BUSINESS_FLOW: (
        "{{ business_flow_description }}\n\n"
        "![Flow Proses Bisnis]({{ diagrams.business_process_flow_image }})"
        "{{ diagrams.business_process_flow_attr }}\n\n"
        "{% for step in business_flow_steps %}\n"
        "{{ loop.index }}. {{ step }}\n"
        "{% endfor %}"
    ),

    # Use case: gambar use-case + satu blok per use case (heading anak + tabel +
    # kriteria). Baris kosong sebelum `###` dan sebelum list WAJIB (blank_before_
    # header / list) — kalau tidak, heading/kriteria bocor jadi teks literal.
    USE_CASES: (
        # SATU diagram use case gabungan (semua aktor dalam satu gambar). Selaras
        # dengan template default/premco.
        "![Use Case Diagram]({{ diagrams.use_case_diagram_image }}){{ diagrams.use_case_diagram_attr }}\n\n"
        "{% for uc in use_cases %}\n"
        "### {{ uc.use_case_id }} — {{ uc.actor }}\n\n"
        "| Field | Isi |\n"
        "|-------|--------------------------------|\n"
        "| No. Use Case | {{ uc.use_case_id }} |\n"
        "| Actor | {{ uc.actor }} |\n"
        "| Pre-Condition | {{ uc.pre_condition }} |\n"
        "| Description | {{ uc.description }} |\n\n"
        "**Acceptance Criteria:**\n\n"
        "{% for criterion in uc.acceptance_criteria %}\n"
        "{{ loop.index }}. {{ criterion }}\n"
        "{% endfor %}\n"
        "{% endfor %}"
    ),

    ACTIVITY_DIAGRAMS: (
        "{% for activity in diagrams.activity_diagrams %}\n"
        "### {{ activity.activity_name }}\n\n"
        "{{ activity.description }}\n\n"
        "![Activity Diagram {{ activity.activity_name }}]({{ activity.image_path }})"
        "{{ activity.image_attr }}\n\n"
        "| Field | Isi |\n"
        "|-------|--------------------------------|\n"
        '| No. Activity Diagram | ACT{{ "%03d" | format(loop.index) }} |\n'
        "| Actor | {{ activity.actor }} |\n"
        "| System | {{ project_name }} |\n"
        "| Pre-Condition | {{ activity.pre_condition }} |\n\n"
        "**Description:**\n\n"
        "{% for step in activity.steps %}\n"
        "{{ loop.index }}. {{ step }}\n"
        "{% endfor %}\n"
        "{% endfor %}"
    ),

    # Test-case dikelompokkan per modul/layar (butuh context `uat_test_groups`).
    # TANPA marker warna: header diwarnai reference.docx tersintesis (spec-driven).
    TEST_GROUPS: (
        "{% for group in uat_test_groups %}\n"
        "**Case Pengujian{% if group.group_name %}: {{ group.group_name }}{% endif %}**\n\n"
        "| No | Role | Kegiatan | Langkah-Langkah Pengujian | Hasil yang Diharapkan | Penguji | Status |\n"
        "|:--:|------|----------|---------------------------|-----------------------|---------|--------|\n"
        "{% for tc in group.test_cases -%}\n"
        "| {{ loop.index }} | {{ tc.role }} | {{ tc.activity }} | {{ tc.steps }} | {{ tc.expected_result }} | | |\n"
        "{% endfor %}\n"
        "{% endfor %}"
    ),

    MANUAL: "*(diisi manual)*",
}


def generate_jinja_template(mapping: list[dict]) -> str:
    """Rencana pemetaan (dari `propose_mapping`, mungkin sudah disunting) →
    string template Jinja `.md`. Deterministik ($0).

    Bab dengan binding yang memiliki sub-struktur sendiri (use case, activity,
    test group, dsb.) MEMBUANG anak-anak bab yang di-upload di bawahnya —
    digantikan isi turunan-kode. Judul dokumen sengaja TIDAK diemisikan (datang
    dari metadata pandoc, seperti template lain).
    """
    blocks: list[str] = []
    skip_below: int | None = None

    for entry in mapping:
        level = entry.get("level", 1)
        text = (entry.get("text") or "").strip()
        binding = entry.get("binding", MANUAL)

        if skip_below is not None:
            if level > skip_below:
                continue                 # anak dari bab yang isinya sudah diganti
            skip_below = None

        if binding == SKIP or not text or level == 0:
            continue

        heading = "#" * min(max(level, 1), 3) + " " + text

        if binding == HEADING_ONLY:
            blocks.append(heading)
            continue

        body = _BODY.get(binding, _BODY[MANUAL])
        blocks.append(heading + "\n\n" + body)
        if binding in _OWNS_SUBTREE:
            skip_below = level

    # Satu baris kosong antar-blok (blank_before_header terpenuhi), diakhiri newline.
    return "\n\n".join(blocks) + "\n"
