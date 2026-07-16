"""Test compiler_service.py (Peran 3) — render Jinja2 + Mermaid + export docx.

Mermaid.ink selalu di-mock supaya test tidak bergantung pada koneksi internet
atau layanan pihak ketiga yang tidak stabil.
"""

import base64
import json
import re
import uuid
import zlib
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
from docx import Document
from docx.oxml.ns import qn

from app.domain.exceptions import DiagramRenderError
from app.services import compiler_service

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "dummy_data"

# PNG 1x1 minimal yang valid, supaya pandoc bisa benar-benar embed gambarnya
# ke docx (bukan cuma byte sembarang).
_MINIMAL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001"
    "08060000001f15c489000000104944415478da6360000002"
    "0001000500010d0a2db40000000049454e44ae426082"
)


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
def mock_mermaid_ok():
    response = Mock()
    response.content = _MINIMAL_PNG
    response.raise_for_status = Mock()
    with patch("app.services.compiler_service.requests.get", return_value=response) as mocked:
        yield mocked


@pytest.fixture(autouse=True)
def redirect_output_dir(tmp_path, monkeypatch):
    """Jangan tulis file test ke system temp asli, pakai folder sementara pytest."""
    monkeypatch.setattr(compiler_service, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(compiler_service, "IMAGES_DIR", tmp_path / "images")


def test_generate_docx_sdd_produces_valid_docx(mock_mermaid_ok):
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data, project_name="Test Project")

    assert Path(output_path).exists()
    doc = Document(output_path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Solution Design Document" in full_text
    assert data["app_description"] in full_text


def test_generate_docx_uat_produces_valid_docx(mock_mermaid_ok):
    data = _load_fixture("document_content_uat.json")

    output_path = compiler_service.generate_docx("UAT", data, project_name="Test Project")

    assert Path(output_path).exists()
    doc = Document(output_path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "User Acceptance Testing" in full_text


def test_generate_docx_lowercase_type_still_works(mock_mermaid_ok):
    """document_type harus case-insensitive ('sdd' == 'SDD')."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("sdd", data)

    assert Path(output_path).exists()


def test_generate_docx_invalid_type_raises_value_error():
    data = _load_fixture("document_content_sdd.json")

    with pytest.raises(ValueError):
        compiler_service.generate_docx("BUKAN_TIPE_VALID", data)


def test_mermaid_unreachable_raises_diagram_render_error():
    data = _load_fixture("document_content_sdd.json")

    with patch(
        "app.services.compiler_service.requests.get",
        side_effect=requests.ConnectionError("mermaid.ink tidak terjangkau"),
    ):
        with pytest.raises(DiagramRenderError, match="tidak merespons"):
            compiler_service.generate_docx("SDD", data)


def _decode_pako_url(url: str) -> str:
    """Balik URL 'pako:' jadi script Mermaid aslinya, untuk verifikasi test."""
    payload = url.split("/img/pako:", 1)[1]
    return json.loads(zlib.decompress(base64.urlsafe_b64decode(payload)))["code"]


def test_mermaid_url_uses_pako_and_round_trips(mock_mermaid_ok):
    """Encoding harus 'pako:' (terkompresi), dan script harus bisa dibalik utuh.

    Ini yang menahan URL di bawah batas ~8KB mermaid.ink; encoding base64 polos
    sebelumnya menembus batas itu pada repo besar dan dijawab HTTP 414.
    """
    data = _load_fixture("document_content_sdd.json")

    compiler_service.generate_docx("SDD", data)

    url = mock_mermaid_ok.call_args_list[0].args[0]
    assert "/img/pako:" in url
    assert _decode_pako_url(url) == data["diagrams"]["system_architecture"]


def test_pako_keeps_large_diagram_under_url_limit(mock_mermaid_ok):
    """Diagram besar yang dulu bikin 414 harus lolos batas panjang URL."""
    big_script = "graph LR\n" + "\n".join(
        f"N{i}[Service Node Number {i}]-->N{i + 1}[Service Node Number {i + 1}]"
        for i in range(120)
    )
    plain_b64_len = len(base64.urlsafe_b64encode(big_script.encode()))

    compiler_service._render_mermaid_to_image(big_script, compiler_service.IMAGES_DIR)

    url = mock_mermaid_ok.call_args_list[0].args[0]
    assert plain_b64_len > compiler_service._MERMAID_URL_LIMIT  # dulu: 414
    assert len(url) < compiler_service._MERMAID_URL_LIMIT  # sekarang: muat


def test_oversized_diagram_fails_before_hitting_network(mock_mermaid_ok):
    """Kalau tetap kebesaran walau dikompresi, gagal dengan pesan jelas dan
    jangan buang-buang request ke mermaid.ink."""
    # Teks acak supaya tidak bisa dikompresi -- meniru diagram yang benar-benar besar.
    incompressible = "graph LR\n" + "\n".join(uuid.uuid4().hex for _ in range(600))

    with pytest.raises(DiagramRenderError, match="terlalu besar"):
        compiler_service._render_mermaid_to_image(incompressible, compiler_service.IMAGES_DIR)

    mock_mermaid_ok.assert_not_called()


def test_http_error_message_names_the_real_status():
    """Sebab asli (mis. 414) harus tersebut, bukan diratakan jadi 'tidak merespons'
    -- persis penyamaran itu yang dulu bikin bug ini lama tak terdiagnosis."""
    response = Mock(status_code=414)
    error = requests.HTTPError("414 Client Error", response=response)
    response.raise_for_status = Mock(side_effect=error)

    with patch("app.services.compiler_service.requests.get", return_value=response):
        with pytest.raises(DiagramRenderError, match="414"):
            compiler_service._render_mermaid_to_image("graph LR\nA-->B", compiler_service.IMAGES_DIR)


def test_code_fence_is_stripped_before_encoding(mock_mermaid_ok):
    """LLM kadang membungkus script dengan ```mermaid -- fence bikin 400."""
    compiler_service._render_mermaid_to_image(
        "```mermaid\ngraph LR\nA-->B\n```", compiler_service.IMAGES_DIR
    )

    url = mock_mermaid_ok.call_args_list[0].args[0]
    assert _decode_pako_url(url) == "graph LR\nA-->B"


# --- Metadata dokumen (isian manusia dari form) ---


def test_sdd_metadata_leaves_no_manual_placeholder(mock_mermaid_ok):
    """Inti dari fitur ini: 17 field form harus menutup SEMUA lubang SDD yang
    bukan tanda tangan. Kalau ada field template yang lupa dipetakan ke form,
    penandanya akan tersisa dan test ini merah."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx(
        "SDD", data, project_name="Test Project", document_metadata=_FULL_SDD_METADATA
    )

    assert _PLACEHOLDER_IN_DOCX not in _docx_text(output_path)


def test_uat_metadata_leaves_no_manual_placeholder(mock_mermaid_ok):
    """Pasangan test di atas untuk UAT: 8 field menutup 8 lubang non-tanda-tangan."""
    data = _load_fixture("document_content_uat.json")

    output_path = compiler_service.generate_docx(
        "UAT", data, project_name="Test Project", document_metadata=_FULL_UAT_METADATA
    )

    assert _PLACEHOLDER_IN_DOCX not in _docx_text(output_path)


def test_metadata_values_appear_in_docx(mock_mermaid_ok):
    """Field tidak cuma menghapus penanda -- isinya harus benar-benar mendarat,
    termasuk yang di dalam sel tabel (Demografi, checklist Security)."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx(
        "SDD", data, document_metadata=_FULL_SDD_METADATA
    )

    text = _docx_text(output_path)
    for value in _FULL_SDD_METADATA.values():
        assert value in text, f"metadata {value!r} tidak muncul di docx"


def test_without_metadata_falls_back_to_old_behaviour(mock_mermaid_ok):
    """Perilaku lama adalah LANTAI, bukan langit: tidak mengisi form sama sekali
    harus menghasilkan dokumen seperti sebelum form ini ada, bukan error atau
    sel kosong melompong."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data, project_name="Test Project")

    assert _PLACEHOLDER_IN_DOCX in _docx_text(output_path)


def test_blank_metadata_fields_treated_as_unfilled(mock_mermaid_ok):
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


def test_sdd_carries_acuan_skeleton_sections(mock_mermaid_ok):
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


def test_uat_has_no_mockup_section(mock_mermaid_ok):
    """Bab Mockup cuma milik SDD — dokumen acuan UAT tidak punya, dan bab
    placeholder yang tidak relevan itu halaman hampa (pelajaran Daftar Gambar)."""
    data = _load_fixture("document_content_uat.json")

    output_path = compiler_service.generate_docx("UAT", data)

    assert "Mockup" not in _docx_text(output_path)


def test_signature_blocks_survive_full_metadata(mock_mermaid_ok):
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


def test_sdd_figures_are_numbered_in_document_order(mock_mermaid_ok):
    """Fixture punya 1 activity diagram -> 3 gambar tetap + 1 = Gambar 1..4."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    assert _captions(output_path, "Image Caption") == [
        "Gambar 1 Arsitektur Sistem",
        "Gambar 2 Integrasi Komponen",
        "Gambar 3 Use Case Diagram",
        "Gambar 4 Activity Diagram Proses Tambah Item Inventaris",
    ]


def test_sdd_tables_are_numbered_in_document_order(mock_mermaid_ok):
    """Fixture punya 1 use case -> 3 tabel tetap + 1 = Tabel 1..4."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    assert _captions(output_path, "Table Caption") == [
        "Tabel 1 Informasi Demografi Aplikasi",
        "Tabel 2 Application Security",
        "Tabel 3 Application Features Requirement",
        "Tabel 4 Use Case UC-01 — Admin",
    ]


def test_numbering_offset_holds_when_loop_grows(mock_mermaid_ok):
    """Penjaga paling penting: offset `+3` di template. Loop activity diagram &
    use case harus MELANJUTKAN penomoran gambar/tabel tetap, bukan mulai dari 1.

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
    assert figure_numbers == ["1", "2", "3", "4", "5", "6"]  # 3 tetap + 3 activity
    assert table_numbers == ["1", "2", "3", "4", "5"]  # 3 tetap + 2 use case


def test_front_matter_tables_are_not_captioned(mock_mermaid_ok):
    """Informasi Dokumen & Revision History sengaja tanpa caption — dokumen acuan
    pun tidak menomorinya, dan penomoran isi mulai dari Informasi Demografi."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    captions = " | ".join(_captions(output_path, "Table Caption"))
    assert "Informasi Dokumen" not in captions
    assert "Revision History" not in captions
    assert captions.startswith("Tabel 1 Informasi Demografi")


def test_docx_carries_indonesian_list_headings(mock_mermaid_ok):
    """Judulnya Indonesia lewat DUA mekanisme Pandoc yang berbeda: `lang=id`
    menerjemahkan Daftar Gambar/Tabel (`lof-title`/`lot-title` DIABAIKAN writer
    docx), sementara Daftar Isi justru cuma bisa lewat `toc-title` dan tidak ikut
    `lang`. Kalau salah satu argumen hilang, judulnya balik jadi Inggris."""
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


def test_uat_has_no_empty_figure_and_table_lists(mock_mermaid_ok):
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


def test_docx_embeds_word_field_codes_for_the_lists(mock_mermaid_ok):
    """Daftar Gambar/Tabel ditulis sebagai FIELD CODE, bukan teks jadi — itu yang
    membuat WORD menghitung nomor halamannya sendiri, sehingga kita tidak perlu
    tahu pagination dari sisi Markdown. Sudah diverifikasi manual di Word: 11
    baris + nomor halaman muncul tanpa refresh."""
    data = _load_fixture("document_content_sdd.json")

    xml = _document_xml(compiler_service.generate_docx("SDD", data))

    # r-string wajib: `\t` di string biasa jadi karakter TAB, sementara
    # `\h`/`\z`/`\c` kebetulan bukan escape sehingga lolos apa adanya — jadi satu
    # dari empat backslash berubah diam-diam dan assertion-nya tidak pernah cocok.
    assert r'TOC \h \z \t &quot;Image Caption&quot; \c' in xml
    assert r'TOC \h \z \t &quot;Table Caption&quot; \c' in xml


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


def test_generated_docx_has_numbered_pages(mock_mermaid_ok):
    """Rantai lengkap: footer di reference.docx harus benar-benar sampai ke
    dokumen yang dihasilkan DAN terpasang ke halamannya (`footerReference`) —
    bukan sekadar ikut menumpang di dalam paketnya."""
    import zipfile

    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    package = zipfile.ZipFile(output_path)
    assert [n for n in package.namelist() if "footer" in n]
    assert "footerReference" in _document_xml(output_path)


def test_document_title_lands_in_both_places(mock_mermaid_ok):
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


def test_uat_gets_its_own_title(mock_mermaid_ok):
    uat = _load_fixture("document_content_uat.json")

    output_path = compiler_service.generate_docx("UAT", uat, project_name="Esteler App")

    from docx import Document

    titles = [p.text for p in Document(output_path).paragraphs if p.style.name == "Title"]
    assert titles == ["Dokumen User Acceptance Testing (UAT) — Esteler App"]


def test_title_without_project_name_stays_clean():
    """project_name kosong -> jangan tinggalkan em-dash menggantung."""
    assert compiler_service._document_title("SDD", "") == "Solution Design Document"
    assert compiler_service._document_title("SDD", "   ") == "Solution Design Document"


def test_pandoc_styles_survive_the_reference_doc(mock_mermaid_ok):
    """reference.docx dibangun DARI kerangka bawaan Pandoc, bukan dari nol —
    Pandoc mencari nama style tertentu, dan kerangka buatan sendiri yang
    kehilangan salah satunya merusak Daftar Gambar/Tabel TANPA error apa pun."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data)

    assert len(_captions(output_path, "Image Caption")) == 4
    assert len(_captions(output_path, "Table Caption")) == 4


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


def test_diagrams_are_lossless_not_jpeg(mock_mermaid_ok):
    """Akar "diagram blur": endpoint /img/ mermaid.ink membalas **JPEG** secara
    default. JPEG itu lossy dan dirancang untuk foto — dipakai untuk line art, dia
    menaruh artefak di sekeliling tiap garis dan huruf. Filenya bahkan sempat
    disimpan berakhiran .png padahal isinya JPEG, yang menyembunyikan masalahnya
    dari siapa pun yang cuma melihat nama file."""
    compiler_service._render_mermaid_to_image("graph LR\n A-->B", compiler_service.IMAGES_DIR)

    url = mock_mermaid_ok.call_args_list[0].args[0]
    assert "type=png" in url


def test_diagrams_are_rendered_large_enough_to_print(mock_mermaid_ok):
    """Diagram bawaan mermaid.ink terukur serendah 381 px lebarnya; direntangkan
    ke ruang halaman 6,5 inci itu ~59 dpi. Cetak layak butuh ~150."""
    compiler_service._render_mermaid_to_image("graph LR\n A-->B", compiler_service.IMAGES_DIR)

    url = mock_mermaid_ok.call_args_list[0].args[0]
    assert "width=1600" in url  # 1600 / 6.5 inci = ~246 dpi


def test_tall_diagram_is_capped_by_height_not_width(tmp_path):
    """Activity diagram itu TINGGI DAN SEMPIT. Kalau semua gambar direntangkan
    selebar halaman, yang tinggi jadi setinggi 17 inci di halaman 11 inci —
    terukur pada esteler: 5 dari 11 diagram tumpah keluar halaman."""
    from PIL import Image

    tall = tmp_path / "tall.png"
    Image.new("RGB", (400, 2000), "white").save(tall)

    assert compiler_service._image_attr(str(tall)) == "{height=8.0in}"


def test_wide_diagram_is_capped_by_width(tmp_path):
    from PIL import Image

    wide = tmp_path / "wide.png"
    Image.new("RGB", (1600, 500), "white").save(wide)

    assert compiler_service._image_attr(str(wide)) == "{width=6.5in}"


def test_every_diagram_fits_on_the_page(mock_mermaid_ok):
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


def test_acceptance_criteria_render_as_a_real_numbered_list(mock_mermaid_ok):
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


def test_use_case_headings_survive_after_criteria_list(mock_mermaid_ok):
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


def test_front_matter_is_separated_from_the_body(mock_mermaid_ok):
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


def test_typography_reaches_the_generated_document(mock_mermaid_ok):
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
