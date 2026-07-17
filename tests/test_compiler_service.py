"""Test compiler_service.py (Peran 3) — render Jinja2 + PlantUML + export docx.

Proses plantuml.jar selalu di-mock (lewat _run_plantuml) supaya test tidak
bergantung pada Java/jar terpasang — normalisasi script dan penulisan file
tetap teruji asli.
"""

import json
import re
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import Mock, patch

import pytest
from docx import Document
from docx.oxml.ns import qn

from app.domain.exceptions import DiagramRenderError
from app.services import compiler_service

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "dummy_data"

def _white_png(width: int, height: int) -> bytes:
    """PNG putih valid berukuran sungguhan, dibangkitkan Pillow.

    Dulu fixture-nya PNG 1x1 hex-embedded — tapi sejak _image_attr menghitung
    ukuran tampil dari piksel (aturan jangan-upscale), gambar 1 piksel
    menghasilkan width=0.00in yang tidak mewakili diagram nyata mana pun.
    PlantUML pada 300 dpi tidak pernah menghasilkan gambar sekecil itu.
    """
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


# Ukuran khas diagram PlantUML nyata pada 300 dpi: muat di halaman tanpa perlu
# diciutkan (1600/360 x 1200/360 = 4,44 x 3,33 inci).
_MINIMAL_PNG = _white_png(1600, 1200)


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _docx_text(path: str) -> str:
    """Semua teks docx, TERMASUK isi tabel.

    doc.paragraphs saja tidak cukup: hampir semua metadata mendarat di sel tabel
    (Informasi Dokumen, Demografi, checklist Security), dan sel tabel tidak ikut
    di doc.paragraphs -- assertion-nya akan hijau palsu.
    """
    doc = Document(path)
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


# Penanda *(diisi manual)* itu Markdown italic -- pandoc mengubah bintangnya jadi
# format, jadi yang tersisa di docx cuma teksnya.
_PLACEHOLDER_IN_DOCX = "(diisi manual)"

# Semua field metadata yang dipakai template SDD (17) dan UAT (8). Sengaja ditulis
# lengkap: test "tidak ada lubang tersisa" di bawah cuma bermakna kalau daftar ini
# memang utuh.
_FULL_SDD_METADATA = {
    "solution_design_no": "SD-2026-014",
    "rfc_number": "RFC-2026-088",
    "version": "1.2",
    "document_classification": "Internal",
    "dev_system_type": "NON ERP",
    "business_requestor": "Divisi Operasional",
    "business_user": "Tim Gudang",
    "projected_user_number": "120 pengguna",
    "value_rp": "Rp 450.000.000",
    "coverage_area": "Nasional",
    "collaboration_profile": "Internal + vendor",
    "technology_capability": "Web + mobile",
    "how_to_access": "https://inventaris.internal/login",
    "infrastructure_capacity": "3 VM, 8 vCPU, 16 GB RAM",
    "security_penetration_test": "Sudah, 2026-06-30",
    "security_secure_coding": "Mengikuti OWASP ASVS L2",
    "security_reverse_proxy": "Nginx",
}

_FULL_UAT_METADATA = {
    "related_rfc_number": "RFC-2026-088",
    "related_work_order": "WO-2026-451",
    "change_owner": "Budi Santoso",
    "prepared_by": "Siti Rahma",
    "preparation_date": "2026-07-10",
    "reviewed_by": "Andi Wijaya",
    "review_date": "2026-07-12",
    "distribution_list": "Tim QA, Tim Operasional",
}


@pytest.fixture
def mock_plantuml_ok():
    """Mock PROSES EKSTERNAL-nya saja (_run_plantuml): normalisasi script,
    penulisan file, dan seluruh alur template tetap berjalan asli."""
    with patch(
        "app.services.compiler_service._run_plantuml", return_value=_MINIMAL_PNG
    ) as mocked:
        yield mocked


@pytest.fixture(autouse=True)
def redirect_output_dir(tmp_path, monkeypatch):
    """Jangan tulis file test ke system temp asli, pakai folder sementara pytest."""
    monkeypatch.setattr(compiler_service, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(compiler_service, "IMAGES_DIR", tmp_path / "images")


def test_generate_docx_sdd_produces_valid_docx(mock_plantuml_ok):
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data, project_name="Test Project")

    assert Path(output_path).exists()
    doc = Document(output_path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Solution Design Document" in full_text
    assert data["app_description"] in full_text


def test_generate_docx_uat_produces_valid_docx(mock_plantuml_ok):
    data = _load_fixture("document_content_uat.json")

    output_path = compiler_service.generate_docx("UAT", data, project_name="Test Project")

    assert Path(output_path).exists()
    doc = Document(output_path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "User Acceptance Testing" in full_text


def test_generate_docx_lowercase_type_still_works(mock_plantuml_ok):
    """document_type harus case-insensitive ('sdd' == 'SDD')."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("sdd", data)

    assert Path(output_path).exists()


def test_generate_docx_invalid_type_raises_value_error():
    data = _load_fixture("document_content_sdd.json")

    with pytest.raises(ValueError):
        compiler_service.generate_docx("BUKAN_TIPE_VALID", data)


def test_missing_jar_raises_diagram_render_error(tmp_path, monkeypatch):
    """plantuml.jar yang tidak ada harus gagal dengan pesan yang menyebut CARA
    memperbaikinya (unduh dari mana, taruh di mana) — bukan FileNotFoundError
    mentah dari subprocess."""
    monkeypatch.setattr(
        compiler_service.config, "PLANTUML_JAR", str(tmp_path / "tidak-ada.jar")
    )

    with pytest.raises(DiagramRenderError, match="plantuml.jar tidak ditemukan"):
        compiler_service._run_plantuml("@startuml\nA --> B\n@enduml")


def test_plantuml_failure_carries_stderr():
    """Sebab asli dari PlantUML (pesan syntax error di stderr) harus tersebut,
    bukan diratakan — kelas penyamaran yang sama dengan 502 yang dulu menelan
    414 mermaid.ink: sebab asli tertelan gejala."""
    failed = CompletedProcess(
        args=[], returncode=1, stdout=b"", stderr=b"Syntax Error on line 3"
    )

    with patch("app.services.compiler_service.subprocess.run", return_value=failed):
        with pytest.raises(DiagramRenderError, match="Syntax Error on line 3"):
            compiler_service._run_plantuml("@startuml\nrusak\n@enduml")


def test_error_image_with_nonzero_exit_is_rejected():
    """PlantUML MENGGAMBAR pesan syntax error sebagai PNG (exit code tetap
    non-nol). Kalau cuma percaya stdout, gambar error itu ter-embed diam-diam ke
    dokumen sebagai 'diagram' — exit code harus tetap diperiksa."""
    error_drawn_as_png = CompletedProcess(
        args=[], returncode=200, stdout=_MINIMAL_PNG, stderr=b"ERROR line 2"
    )

    with patch("app.services.compiler_service.subprocess.run", return_value=error_drawn_as_png):
        with pytest.raises(DiagramRenderError, match="ERROR line 2"):
            compiler_service._run_plantuml("@startuml\nrusak\n@enduml")


def test_render_receives_normalized_source(mock_plantuml_ok):
    """Script LLM harus dinormalisasi sebelum sampai ke plantuml.jar: fence
    dibuang, terbungkus @startuml, dan preamble gaya (theme + dpi) tersuntik —
    gaya visual datang dari SATU tempat deterministik, bukan dari LLM."""
    compiler_service._render_diagram_to_image(
        "```plantuml\n@startuml\nAdmin --> UC1\n@enduml\n```",
        compiler_service.IMAGES_DIR,
    )

    source = mock_plantuml_ok.call_args_list[0].args[0]
    assert "```" not in source
    assert source.startswith("@startuml")
    assert "!theme plain" in source
    assert "Admin --> UC1" in source


def test_bare_script_gets_wrapped(mock_plantuml_ok):
    """Script tanpa @startuml (LLM lupa) tetap harus jadi source yang valid."""
    compiler_service._render_diagram_to_image("A --> B", compiler_service.IMAGES_DIR)

    source = mock_plantuml_ok.call_args_list[0].args[0]
    assert source.startswith("@startuml")
    assert source.rstrip().endswith("@enduml")
    assert "A --> B" in source


# --- Metadata dokumen (isian manusia dari form) ---


def test_sdd_metadata_leaves_no_manual_placeholder(mock_plantuml_ok):
    """Inti dari fitur ini: 17 field form harus menutup SEMUA lubang SDD yang
    bukan tanda tangan. Kalau ada field template yang lupa dipetakan ke form,
    penandanya akan tersisa dan test ini merah."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx(
        "SDD", data, project_name="Test Project", document_metadata=_FULL_SDD_METADATA
    )

    assert _PLACEHOLDER_IN_DOCX not in _docx_text(output_path)


def test_uat_metadata_leaves_no_manual_placeholder(mock_plantuml_ok):
    """Pasangan test di atas untuk UAT: 8 field menutup 8 lubang non-tanda-tangan."""
    data = _load_fixture("document_content_uat.json")

    output_path = compiler_service.generate_docx(
        "UAT", data, project_name="Test Project", document_metadata=_FULL_UAT_METADATA
    )

    assert _PLACEHOLDER_IN_DOCX not in _docx_text(output_path)


def test_metadata_values_appear_in_docx(mock_plantuml_ok):
    """Field tidak cuma menghapus penanda -- isinya harus benar-benar mendarat,
    termasuk yang di dalam sel tabel (Demografi, checklist Security)."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx(
        "SDD", data, document_metadata=_FULL_SDD_METADATA
    )

    text = _docx_text(output_path)
    for value in _FULL_SDD_METADATA.values():
        assert value in text, f"metadata {value!r} tidak muncul di docx"


def test_without_metadata_falls_back_to_old_behaviour(mock_plantuml_ok):
    """Perilaku lama adalah LANTAI, bukan langit: tidak mengisi form sama sekali
    harus menghasilkan dokumen seperti sebelum form ini ada, bukan error atau
    sel kosong melompong."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data, project_name="Test Project")

    assert _PLACEHOLDER_IN_DOCX in _docx_text(output_path)


def test_blank_metadata_fields_treated_as_unfilled(mock_plantuml_ok):
    """Form mengirim string kosong untuk input yang tidak disentuh (dan Pydantic
    mengirim None untuk field yang absen). Keduanya harus jatuh ke penanda --
    bukan bikin sel tabel kosong yang terbaca seperti bug."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx(
        "SDD",
        data,
        document_metadata={"rfc_number": "   ", "version": "", "document_classification": None},
    )

    assert _PLACEHOLDER_IN_DOCX in _docx_text(output_path)


def test_sdd_carries_acuan_skeleton_sections(mock_plantuml_ok):
    """Kerangka bagian manual yang meniru dokumen acuan (halaman muka, Timeline,
    Cost Estimation, blok tanda tangan, bab Mockup) harus ada di SDD sebagai
    kerangka KOSONG — bukan penanda (diisi manual), karena tidak dipetakan ke
    form; konvensinya sama dengan Revision History yang di acuan pun kosong.
    Dipanggil dengan metadata LENGKAP supaya sekalian membuktikan kerangka ini
    tidak menabrak test "tidak ada penanda tersisa"."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx(
        "SDD", data, document_metadata=_FULL_SDD_METADATA
    )

    text = _docx_text(output_path)
    for anchor in [
        "Katalog Proses Bisnis",
        "Business Process Owner",
        "Gathering Requirement",
        "Cost Estimation",
        "Perwakilan User",
        "Perwakilan Pengembang",
        "Mockup Antarmuka",
    ]:
        assert anchor in text, f"kerangka acuan {anchor!r} hilang dari SDD"
    assert _PLACEHOLDER_IN_DOCX not in text


def test_uat_has_no_mockup_section(mock_plantuml_ok):
    """Bab Mockup cuma milik SDD — dokumen acuan UAT tidak punya, dan bab
    placeholder yang tidak relevan itu halaman hampa (pelajaran Daftar Gambar)."""
    data = _load_fixture("document_content_uat.json")

    output_path = compiler_service.generate_docx("UAT", data)

    assert "Mockup" not in _docx_text(output_path)


def test_signature_blocks_survive_full_metadata(mock_plantuml_ok):
    """Blok tanda tangan & sertifikasi hasil sengaja TIDAK ditanyakan di form:
    tanda tangan bukan data yang diketik, dan hasil Lolos/Gagal belum ada saat
    generate. Metadata selengkap apa pun tidak boleh menghapusnya."""
    uat = _load_fixture("document_content_uat.json")

    output_path = compiler_service.generate_docx(
        "UAT", uat, document_metadata=_FULL_UAT_METADATA
    )

    text = _docx_text(output_path)
    assert "tanda tangan" in text.lower()
    assert "Sertifikasi Keberhasilan Pelaksanaan Pengujian" in text


# --- Daftar Gambar & Daftar Tabel ---------------------------------------------
#
# Nomor gambar/tabel DITANAM di teks caption oleh template ("Gambar 4 ..."), dan
# Word cuma mengumpulkannya ke Daftar Gambar/Tabel sambil menambahkan nomor
# HALAMAN. Konsekuensinya: kalau urutan atau offset di template meleset, tidak
# ada error apa pun — dokumennya cuma salah nomor. Test di bawah yang menjaganya.
#
# Kenapa ini penting: di dokumen acuan 87 halaman yang jadi model produk ini,
# Daftar Gambar/Tabel justru DUA bagian yang rusak (seluruh entrinya menyebut
# aplikasi lain, nomornya lompat & dobel) — persis karena mekanis dan tidak ada
# yang memeriksa. Di sinilah produk ini melampaui acuannya, jadi jangan sampai
# kita mengulangi kesalahan yang sama.


def _captions(output_path: str, style: str) -> list[str]:
    from docx import Document

    return [p.text for p in Document(output_path).paragraphs if p.style.name == style]


def _document_xml(output_path: str) -> str:
    import zipfile

    return zipfile.ZipFile(output_path).read("word/document.xml").decode("utf-8", "ignore")


def test_sdd_figures_are_numbered_in_document_order(mock_plantuml_ok):
    """Fixture punya 1 activity diagram -> 4 gambar tetap + 1 = Gambar 1..5."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    assert _captions(output_path, "Image Caption") == [
        "Gambar 1 Arsitektur Sistem",
        "Gambar 2 Integrasi Komponen",
        "Gambar 3 Flow Proses Bisnis",
        "Gambar 4 Use Case Diagram",
        "Gambar 5 Activity Diagram Proses Tambah Item Inventaris",
    ]


def test_sdd_tables_are_numbered_in_document_order(mock_plantuml_ok):
    """Fixture punya 1 use case + 1 activity -> 5 tabel tetap + 1 + 1 = Tabel 1..7."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    assert _captions(output_path, "Table Caption") == [
        "Tabel 1 Informasi Role Pengguna",
        "Tabel 2 Informasi Demografi Aplikasi",
        "Tabel 3 System Requirement",
        "Tabel 4 Application Security",
        "Tabel 5 Application Features Requirement",
        "Tabel 6 Use Case UC-01 — Admin",
        "Tabel 7 Activity Diagram Proses Tambah Item Inventaris",
    ]


def test_numbering_offset_holds_when_loop_grows(mock_plantuml_ok):
    """Penjaga paling penting: offset di template. Loop activity diagram &
    use case harus MELANJUTKAN penomoran gambar/tabel tetap, bukan mulai dari 1 —
    dan tabel activity harus melanjutkan DARI tabel use case (offset-nya memuat
    use_cases|length).

    Kalau seseorang menambah gambar/tabel tetap tanpa menaikkan offset-nya,
    nomor akan bentrok DIAM-DIAM — tanpa error, tanpa test lain yang gagal."""
    data = _load_fixture("document_content_sdd.json")
    activity = data["diagrams"]["activity_diagrams"][0]
    use_case = data["use_cases"][0]
    data = {
        **data,
        "diagrams": {**data["diagrams"], "activity_diagrams": [activity, activity, activity]},
        "use_cases": [use_case, use_case],
    }

    output_path = compiler_service.generate_docx("SDD", data)

    figure_numbers = [c.split()[1] for c in _captions(output_path, "Image Caption")]
    table_numbers = [c.split()[1] for c in _captions(output_path, "Table Caption")]
    assert figure_numbers == ["1", "2", "3", "4", "5", "6", "7"]  # 4 tetap + 3 activity
    assert table_numbers == [
        "1", "2", "3", "4", "5",  # tetap
        "6", "7",                 # 2 use case
        "8", "9", "10",           # 3 activity, melanjutkan dari use case
    ]


def test_front_matter_tables_are_not_captioned(mock_plantuml_ok):
    """Informasi Dokumen, Revision History, Timeline, Cost, dan blok tanda tangan
    sengaja tanpa caption — dokumen acuan pun tidak menomorinya; penomoran isi
    mulai dari tabel role pengguna di Deskripsi Aplikasi."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    captions = " | ".join(_captions(output_path, "Table Caption"))
    assert "Informasi Dokumen" not in captions
    assert "Revision History" not in captions
    assert "Timeline" not in captions
    assert "Cost" not in captions
    assert captions.startswith("Tabel 1 Informasi Role Pengguna")


def test_docx_carries_indonesian_list_headings(mock_plantuml_ok):
    """Ketiga judul daftar SDD kini teks template (blok openxml ber-style
    TOCHeading) — bukan lagi hasil `lang=id`/`toc-title`, karena field-nya
    ditanam template sejak posisi daftar dipindah meniru acuan. Yang dijaga
    tetap sama: pembaca melihat judul Indonesia, bukan Inggris."""
    data = _load_fixture("document_content_sdd.json")

    # Yang diperiksa TEKS YANG TERLIHAT (isi <w:t>), bukan XML mentah: string
    # "List of Figures" tetap ada di XML sebagai <w:docPartGallery> — identifier
    # internal Word untuk jenis content control-nya, tidak pernah dilihat pembaca.
    # Meng-assert ke XML mentah berarti menguji proksi, bukan barangnya.
    xml = _document_xml(compiler_service.generate_docx("SDD", data))
    visible = " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))

    assert "Daftar Isi" in visible
    assert "Daftar Gambar" in visible
    assert "Daftar Tabel" in visible
    assert "List of Figures" not in visible
    assert "List of Tables" not in visible


def test_uat_has_no_empty_figure_and_table_lists(mock_plantuml_ok):
    """UAT TIDAK boleh dapat Daftar Gambar/Tabel: dia punya NOL gambar dan cuma
    satu tabel isi (sisanya front-matter yang tidak di-caption), jadi --lof/--lot
    menghasilkan dua halaman indeks KOSONG di tiap dokumen UAT.

    Ini bug nyata yang sempat masuk saat --lof/--lot dipasang global, dan lolos
    karena tidak ada yang menjaganya — semua test lain cuma memeriksa SDD.
    Halaman hampa lebih buruk daripada tidak ada halamannya."""
    uat = _load_fixture("document_content_uat.json")

    output_path = compiler_service.generate_docx("UAT", uat)

    xml = _document_xml(output_path)
    visible = " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))
    assert "Daftar Gambar" not in visible
    assert "Daftar Tabel" not in visible
    assert "Daftar Isi" in visible  # Daftar Isi tetap ada — UAT memang punya bab


def test_docx_embeds_word_field_codes_for_the_lists(mock_plantuml_ok):
    """Daftar Isi/Gambar/Tabel ditulis sebagai FIELD CODE, bukan teks jadi — itu
    yang membuat WORD menghitung nomor halamannya sendiri, sehingga kita tidak
    perlu tahu pagination dari sisi Markdown. Sejak 2026-07-16 field-nya ditanam
    sdd_template.md (bukan --toc/--lof/--lot) supaya posisinya meniru acuan:
    sesudah persetujuan, bukan menempel judul. Instruksinya disalin persis dari
    yang dulu ditulis Pandoc — sudah diverifikasi terisi di Word tanpa refresh."""
    data = _load_fixture("document_content_sdd.json")

    xml = _document_xml(compiler_service.generate_docx("SDD", data))

    # r-string wajib: `\t` di string biasa jadi karakter TAB, sementara
    # `\h`/`\z`/`\c` kebetulan bukan escape sehingga lolos apa adanya — jadi satu
    # dari empat backslash berubah diam-diam dan assertion-nya tidak pernah cocok.
    assert r'TOC \o &quot;1-3&quot; \h \z \u' in xml
    assert r'TOC \h \z \t &quot;Image Caption&quot; \c' in xml
    assert r'TOC \h \z \t &quot;Table Caption&quot; \c' in xml


def test_sdd_carries_updatefields_so_word_fills_the_lists(mock_plantuml_ok):
    """Pasangan test di atas, sisi satunya: field yang ditanam template hanya
    hidup kalau settings.xml membawa updateFields (SDD tidak lagi memakai --toc,
    jadi Pandoc tidak memasangnya sendiri — dia harus datang dari reference.docx,
    yang settings-nya disalin Pandoc ke setiap dokumen; diprobe 2026-07-16).
    Tanpa ini daftar-daftarnya SUNYI: dokumen tetap jadi, field tidak pernah
    terisi, dan pembaca cuma melihat placeholder."""
    import zipfile

    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    settings = zipfile.ZipFile(output_path).read("word/settings.xml").decode("utf-8", "ignore")
    assert "updateFields" in settings


def test_sdd_lists_come_after_persetujuan_like_the_reference(mock_plantuml_ok):
    """Alasan seluruh mekanisme field-di-template: dokumen acuan menaruh cover +
    revisi + persetujuan DULU, daftar-daftar menyusul. --toc memaku Daftar Isi
    tepat sesudah judul (halaman cover) dan tidak bisa dipindah. Kunci urutannya
    lewat teks yang terlihat: 'Persetujuan Dokumen' harus muncul SEBELUM
    'Daftar Isi'."""
    data = _load_fixture("document_content_sdd.json")

    xml = _document_xml(compiler_service.generate_docx("SDD", data))
    visible = " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))

    assert visible.index("Persetujuan Dokumen") < visible.index("Daftar Isi")


def test_table_headers_are_centered(mock_plantuml_ok):
    """Teks header tabel dirata-tengah lewat post-process python-docx — Word
    MENGABAIKAN w:pPr (jc) dari tblStylePr firstRow di table style (diprobe
    dengan compat flag true/false/absen, ketiganya identik), jadi ini tidak bisa
    dititipkan ke reference.docx seperti bold/warna/latar."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    data = _load_fixture("document_content_sdd.json")

    document = Document(compiler_service.generate_docx("SDD", data))

    assert document.tables, "tidak ada tabel di dokumen"
    for table in document.tables:
        for cell in table.rows[0].cells:
            for paragraph in cell.paragraphs:
                assert paragraph.alignment == WD_ALIGN_PARAGRAPH.CENTER, (
                    f"header {paragraph.text!r} tidak rata tengah"
                )


def test_reference_docx_carries_dot_leader_toc_styles():
    """Style "toc 1..3" + "table of figures" TIDAK ada di kerangka bawaan Pandoc
    (diperiksa) — tanpa mendefinisikannya, rupa Daftar Isi (titik-titik sampai
    nomor halaman rata kanan) tergantung selera versi Word pembaca."""
    import zipfile

    styles = (
        zipfile.ZipFile(compiler_service.REFERENCE_DOCX)
        .read("word/styles.xml")
        .decode("utf-8", "ignore")
    )
    for style_id in ("TOC1", "TOC2", "TOC3", "TableofFigures"):
        assert f'w:styleId="{style_id}"' in styles, f"style {style_id} hilang"
    assert 'w:leader="dot"' in styles


# --- Tampilan dokumen (reference.docx) ----------------------------------------
#
# Kerangka bawaan Pandoc TIDAK punya header, footer, maupun nomor halaman
# (diperiksa: `pandoc --print-default-data-file reference.docx` tak berisi footer).
# Itu bukan cuma soal rupa: Daftar Gambar menulis "Gambar 4 ... 14" sementara
# tidak ada halaman yang bertuliskan "14", jadi pembaca harus menghitung dari
# depan. Indeks yang dibangun sesi ini tidak bisa dipakai tanpa ini.


def test_reference_docx_ships_with_the_repo():
    """Penjaga paling penting di blok ini, dan yang paling tidak terduga:
    `.gitignore` punya pola lebar `*.docx` (untuk dokumen hasil generate yang
    mendarat di folder unduhan). Tanpa pengecualian eksplisit, reference.docx
    ikut tertelan — dan SETIAP generate gagal di mesin yang baru clone, sementara
    di mesin yang sudah pernah menjalankan build_reference_docx.py semuanya
    terlihat normal. Persis "works on my machine"."""
    assert compiler_service.REFERENCE_DOCX.exists(), (
        "app/templates/reference.docx hilang. Jalankan: "
        "python scripts/build_reference_docx.py"
    )


def test_reference_docx_carries_a_page_number_footer():
    import zipfile

    package = zipfile.ZipFile(compiler_service.REFERENCE_DOCX)
    footers = [n for n in package.namelist() if "footer" in n]

    assert footers, "reference.docx tidak punya footer"
    footer_xml = package.read(footers[0]).decode("utf-8", "ignore")
    assert "PAGE" in footer_xml
    assert "TITLE" in footer_xml


def test_generated_docx_has_numbered_pages(mock_plantuml_ok):
    """Rantai lengkap: footer di reference.docx harus benar-benar sampai ke
    dokumen yang dihasilkan DAN terpasang ke halamannya (`footerReference`) —
    bukan sekadar ikut menumpang di dalam paketnya."""
    import zipfile

    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    package = zipfile.ZipFile(output_path)
    assert [n for n in package.namelist() if "footer" in n]
    assert "footerReference" in _document_xml(output_path)


def test_document_title_lands_in_both_places(mock_plantuml_ok):
    """Judul dipakai DUA kali: sebagai judul besar halaman pertama (style Title)
    dan sebagai teks kaki tiap halaman (field TITLE membacanya dari docProps).
    Satu sumber, dua tempat — kalau docProps kosong, kaki halaman ikut kosong."""
    import re
    import zipfile

    from docx import Document

    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data, project_name="Esteler App")

    core = zipfile.ZipFile(output_path).read("docProps/core.xml").decode("utf-8", "ignore")
    assert re.search(r"<dc:title>Solution Design Document — Esteler App</dc:title>", core)
    titles = [p.text for p in Document(output_path).paragraphs if p.style.name == "Title"]
    assert titles == ["Solution Design Document — Esteler App"]


def test_uat_gets_its_own_title(mock_plantuml_ok):
    uat = _load_fixture("document_content_uat.json")

    output_path = compiler_service.generate_docx("UAT", uat, project_name="Esteler App")

    from docx import Document

    titles = [p.text for p in Document(output_path).paragraphs if p.style.name == "Title"]
    assert titles == ["Dokumen User Acceptance Testing (UAT) — Esteler App"]


def test_title_without_project_name_stays_clean():
    """project_name kosong -> jangan tinggalkan em-dash menggantung."""
    assert compiler_service._document_title("SDD", "") == "Solution Design Document"
    assert compiler_service._document_title("SDD", "   ") == "Solution Design Document"


def test_pandoc_styles_survive_the_reference_doc(mock_plantuml_ok):
    """reference.docx dibangun DARI kerangka bawaan Pandoc, bukan dari nol —
    Pandoc mencari nama style tertentu, dan kerangka buatan sendiri yang
    kehilangan salah satunya merusak Daftar Gambar/Tabel TANPA error apa pun."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    assert len(_captions(output_path, "Image Caption")) == 5
    assert len(_captions(output_path, "Table Caption")) == 7


# --- Kualitas visual ----------------------------------------------------------
#
# Semua di bawah ini gagal SUNYI: dokumennya tetap jadi, tetap lengkap, tetap
# lolos setiap test lain — cuma jelek atau tak terbaca. Tidak ada satu pun yang
# bisa ditemukan tanpa membuka dokumennya.


def _images(output_path: str):
    import io
    import zipfile

    from PIL import Image

    package = zipfile.ZipFile(output_path)
    return [
        Image.open(io.BytesIO(package.read(n)))
        for n in sorted(package.namelist())
        if "media" in n
    ]


def test_diagrams_are_lossless_not_jpeg(mock_plantuml_ok):
    """Warisan pelajaran "diagram blur" era mermaid.ink: file yang ditulis harus
    benar-benar PNG (lossless — JPEG menaruh artefak di sekeliling line art),
    apa pun yang dikembalikan renderer. Penjaga rantai: byte dari renderer harus
    mendarat utuh di file."""
    path = compiler_service._render_diagram_to_image(
        "@startuml\nA --> B\n@enduml", compiler_service.IMAGES_DIR
    )

    content = Path(path).read_bytes()
    assert content.startswith(b"\x89PNG")
    assert content == _MINIMAL_PNG


def test_diagrams_are_rendered_large_enough_to_print(mock_plantuml_ok):
    """Default PlantUML 96 dpi — cukup untuk layar, buram untuk cetak (layak
    cetak butuh ≥150; era mermaid.ink memakai ~246). Preamble dpi harus benar-benar
    sampai ke source yang dirender."""
    compiler_service._render_diagram_to_image(
        "@startuml\nA --> B\n@enduml", compiler_service.IMAGES_DIR
    )

    source = mock_plantuml_ok.call_args_list[0].args[0]
    assert f"skinparam dpi {compiler_service._PLANTUML_DPI}" in source
    assert compiler_service._PLANTUML_DPI >= 150


def test_tall_diagram_is_capped_by_height_not_width(tmp_path):
    """Activity diagram itu TINGGI DAN SEMPIT. Kalau semua gambar direntangkan
    selebar halaman, yang tinggi jadi setinggi 17 inci di halaman 11 inci —
    terukur pada esteler: 5 dari 11 diagram tumpah keluar halaman."""
    tall = tmp_path / "tall.png"
    tall.write_bytes(_white_png(4000, 20000))

    assert compiler_service._image_attr(str(tall)) == "{height=8.0in}"


def test_wide_diagram_is_capped_by_width(tmp_path):
    wide = tmp_path / "wide.png"
    wide.write_bytes(_white_png(20000, 4000))

    assert compiler_service._image_attr(str(wide)) == "{width=6.5in}"


def test_small_diagram_is_never_upscaled(tmp_path):
    """Diagram kecil yang DIRENTANGKAN selebar halaman jadi buram dengan huruf
    raksasa — dan ukuran teks antar diagram jadi tidak konsisten. Kalau muat,
    pakai ukuran tampil alami (piksel / _DIAGRAM_DISPLAY_DPI), jangan upscale."""
    small = tmp_path / "small.png"
    small.write_bytes(_white_png(1800, 900))

    expected_in = 1800 / compiler_service._DIAGRAM_DISPLAY_DPI
    assert compiler_service._image_attr(str(small)) == f"{{width={expected_in:.2f}in}}"


def test_every_diagram_fits_on_the_page(mock_plantuml_ok):
    """Penjaga rantai: atribut ukuran harus benar-benar sampai ke docx, bukan cuma
    benar di dalam fungsinya sendiri."""
    import re
    import zipfile

    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    xml = zipfile.ZipFile(output_path).read("word/document.xml").decode("utf-8", "ignore")
    emu_per_inch = 914400
    sizes = [
        (int(w) / emu_per_inch, int(h) / emu_per_inch)
        for w, h in re.findall(r'<wp:extent cx="(\d+)" cy="(\d+)"', xml)
    ]
    assert sizes, "tidak ada gambar di dokumen"
    for width, height in sizes:
        assert width <= compiler_service._PAGE_WIDTH_IN + 0.1
        assert height <= compiler_service._PAGE_HEIGHT_IN + 0.1


def test_acceptance_criteria_render_as_a_real_numbered_list(mock_plantuml_ok):
    """Markdown mensyaratkan list didahului BARIS KOSONG. Tanpa itu "1." dianggap
    lanjutan paragraf "Acceptance Criteria:" dan seluruh kriteria dilebur jadi
    satu paragraf gembung — terjadi betulan, dan lolos semua test karena teksnya
    memang ada, cuma tidak terbaca."""
    from docx import Document

    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    paragraphs = list(Document(output_path).paragraphs)
    label = next(i for i, p in enumerate(paragraphs) if p.text.strip() == "Acceptance Criteria:")
    first_item = paragraphs[label + 1]
    ppr = first_item._p.find(qn("w:pPr"))
    assert ppr is not None and ppr.find(qn("w:numPr")) is not None, (
        "kriteria pertama bukan item list bernomor — kemungkinan terlebur ke paragraf"
    )


def test_use_case_headings_survive_after_criteria_list(mock_plantuml_ok):
    """Sisi SEBALIKNYA dari test di atas: Pandoc juga mensyaratkan baris kosong
    SEBELUM heading (blank_before_header). Tanpa itu heading use case berikutnya
    ("### 11.2 ...") menempel di baris kriteria terakhir dan keluar sebagai TEKS
    LITERAL "### ..." di dalam list item — bukan heading, hilang dari Daftar Isi,
    tanpa error. Terjadi betulan pada use case 11.2–11.8 dokumen esteler.

    Fixture cuma punya 1 use case dan bug-nya baru muncul mulai use case KEDUA —
    itu sebabnya dia lolos dari semua test lain. Test ini menumbuhkannya jadi 2."""
    data = _load_fixture("document_content_sdd.json")
    use_case = data["use_cases"][0]
    data = {**data, "use_cases": [use_case, use_case]}

    output_path = compiler_service.generate_docx("SDD", data)

    doc = Document(output_path)
    leaked = [p.text for p in doc.paragraphs if "###" in p.text]
    assert not leaked, f"heading Markdown lolos sebagai teks literal: {leaked}"
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert any(t.startswith("11.2 Use Case") for t in headings), (
        "heading use case kedua tidak menjadi heading sungguhan"
    )


def test_activity_diagram_carries_reference_style_metadata_table(mock_plantuml_ok):
    """Tiap activity diagram di dokumen acuan punya tabel metadata (No. ACT001,
    Actor, System, Pre-Condition) + langkah bernomor — bukan cuma gambar dan satu
    kalimat. Nomor ACT ditanam deterministik dari urutan, bukan diminta ke LLM."""
    data = _load_fixture("document_content_sdd.json")
    activity = data["diagrams"]["activity_diagrams"][0]
    data = {
        **data,
        "diagrams": {**data["diagrams"], "activity_diagrams": [activity, activity]},
    }

    output_path = compiler_service.generate_docx(
        "SDD", data, project_name="Test Project"
    )

    text = _docx_text(output_path)
    assert "ACT001" in text
    assert "ACT002" in text
    assert activity["actor"] in text
    assert activity["pre_condition"] in text
    for step in activity["steps"]:
        assert step in text, f"langkah aktivitas {step!r} hilang dari dokumen"


def test_business_flow_carries_diagram_and_numbered_steps(mock_plantuml_ok):
    """Flow Proses Bisnis di acuan = diagram + tahapan bernomor, bukan satu
    paragraf prosa. Langkahnya harus jadi list bernomor sungguhan (pelajaran
    Acceptance Criteria: tanpa baris kosong, list terlebur jadi paragraf)."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    paragraphs = list(Document(output_path).paragraphs)
    label = next(
        i for i, p in enumerate(paragraphs)
        if p.text.strip() == "Tahapan alur proses bisnis:"
    )
    first_step = paragraphs[label + 1]
    ppr = first_step._p.find(qn("w:pPr"))
    assert ppr is not None and ppr.find(qn("w:numPr")) is not None, (
        "tahapan pertama bukan item list bernomor — kemungkinan terlebur ke paragraf"
    )
    text = _docx_text(output_path)
    for step in data["business_flow_steps"]:
        assert step in text


def test_user_roles_and_system_requirements_land_in_tables(mock_plantuml_ok):
    """Tabel role pengguna (bab 1) dan System Requirement terstruktur (bab 4)
    meniru acuan — isinya harus benar-benar mendarat di sel tabel."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    text = _docx_text(output_path)
    for role in data["user_roles"]:
        assert role["role_name"] in text
        assert role["description"] in text
    for req in data["system_requirements"]:
        assert req["name"] in text
        assert req["detail"] in text


def test_front_matter_is_separated_from_the_body(mock_plantuml_ok):
    """Halaman muka (identitas, riwayat revisi, persetujuan) harus berhenti di
    halamannya sendiri, tidak menyambung ke Deskripsi Aplikasi."""
    import zipfile

    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    xml = zipfile.ZipFile(output_path).read("word/document.xml").decode("utf-8", "ignore")
    assert 'w:type="page"' in xml


def test_table_header_is_black_with_white_text():
    """Dipasang lewat conditional formatting `firstRow` di style Table — BUKAN
    dengan memformat sel langsung. Pandoc menghasilkan sel ber-`<w:tcPr/>` KOSONG
    dan menyalakan `<w:tblLook w:firstRow="1">`, jadi Word sendiri yang menerapkan
    format baris pertama dari style. Artinya seluruh rupa tabel diatur dari satu
    tempat, dan template Jinja2 tidak perlu tahu apa-apa soal warna."""
    import re
    import zipfile

    styles = (
        zipfile.ZipFile(compiler_service.REFERENCE_DOCX)
        .read("word/styles.xml")
        .decode("utf-8", "ignore")
    )
    table = re.search(r'<w:style w:type="table"[^>]*w:styleId="Table".*?</w:style>', styles, re.S)
    first_row = re.search(r"<w:tblStylePr w:type=\"firstRow\">.*?</w:tblStylePr>", table.group(0), re.S)

    assert 'w:fill="000000"' in first_row.group(0)
    assert 'w:color w:val="FFFFFF"' in first_row.group(0)


def test_typography_reaches_the_generated_document(mock_plantuml_ok):
    """Diperiksa lewat python-docx, BUKAN cocok-cocokan string XML: Pandoc menulis
    ulang XML-nya dengan gaya spasi berbeda (`<w:b />` bukan `<w:b/>`), dan
    assertion berbasis string diam-diam gagal karena itu — betulan terjadi."""
    from docx import Document

    data = _load_fixture("document_content_sdd.json")

    document = Document(compiler_service.generate_docx("SDD", data))

    section = document.styles["Heading 2"].font
    assert section.bold and section.all_caps, "judul bab harus tebal & huruf besar"
    caption = document.styles["Image Caption"].font
    assert caption.italic and caption.size.pt <= 10, "caption harus kecil & miring"
