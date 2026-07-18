"""Tes `template_spec_service` (V2 increment 1). Fixture SINTETIS dibangun
python-docx — bukan docx vendor (yang gitignore) — supaya jalan di CI mana pun."""
from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

from app.services.template_spec_service import build_template_spec


def _shade_first_row(table, fill):
    for cell in table.rows[0].cells:
        tc_pr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), fill)
        tc_pr.append(shd)


def _build_synthetic_docx(path):
    doc = Document()
    h1 = doc.styles["Heading 1"]
    h1.font.size = Pt(16)
    h1.font.bold = True
    h1.font.all_caps = True
    h1.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    doc.add_paragraph("Judul Dokumen", style="Title")
    doc.add_paragraph("Bab Satu", style="Heading 1")
    doc.add_paragraph("Sub A", style="Heading 2")
    doc.add_paragraph("Bab Dua", style="Heading 1")
    doc.add_paragraph("", style="Heading 1")   # heading kosong -> dekay
    doc.add_paragraph("Paragraf body biasa untuk mengisi dokumen.")

    table = doc.add_table(rows=2, cols=3)
    table.cell(0, 0).text = "No"
    _shade_first_row(table, "A4A4A4")

    section = doc.add_section(WD_SECTION.NEW_PAGE)
    section.orientation = WD_ORIENT.LANDSCAPE

    doc.save(str(path))
    return path


def test_build_template_spec_menangkap_struktur_dan_visual(tmp_path):
    path = _build_synthetic_docx(tmp_path / "synthetic.docx")
    spec = build_template_spec(path)

    # --- struktur / outline berurut ---
    st = spec["structure"]
    assert st["n_tables"] == 1
    assert st["n_sections"] == 2
    outline = [(o["level"], o["text"]) for o in st["outline"]]
    assert (0, "Judul Dokumen") in outline
    assert (1, "Bab Satu") in outline
    assert (2, "Sub A") in outline
    assert st["heading_usage"]["Heading 1"] == 3   # Bab Satu, Bab Dua, kosong
    assert st["heading_usage"]["Heading 2"] == 1

    # --- dekay: satu heading kosong ---
    assert spec["decay"]["empty_headings"] == 1

    # --- visual: heading terukur (bukan diasumsikan) ---
    h1 = spec["visual"]["headings"]["Heading 1"]
    assert h1["size_pt"] == 16
    assert h1["bold"] is True
    assert h1["caps"] is True
    assert h1["align"] == "left"

    # --- visual: warna header tabel + orientasi landscape ---
    assert spec["visual"]["table_header_fill"] == "A4A4A4"
    assert spec["visual"]["has_landscape"] is True

    # --- font efektif ter-resolve (non-None) ---
    assert spec["visual"]["effective_body_font"]
    assert spec["visual"]["effective_heading_font"]


def test_build_template_spec_dokumen_polos_tanpa_error(tmp_path):
    """Dokumen minimal (tanpa tabel/heading khusus) tetap menghasilkan spec utuh,
    tidak melempar — jalur 'template miskin' yang V0 catat (4/14 style)."""
    doc = Document()
    doc.add_paragraph("Cuma paragraf biasa.")
    p = tmp_path / "polos.docx"
    doc.save(str(p))

    spec = build_template_spec(p)
    assert spec["structure"]["n_tables"] == 0
    assert spec["structure"]["outline"] == []
    assert spec["visual"]["table_header_fill"] is None
    assert spec["visual"]["has_landscape"] is False
    assert spec["visual"]["base_size_pt"]        # selalu ada fallback
