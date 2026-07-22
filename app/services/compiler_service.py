"""
Compiler service (Peran 3 — Backend & Templating).

Alur: DocumentContent (Contract B, dari LLMService milik Peran 2)
      -> render diagram PlantUML jadi gambar (LOKAL, lewat plantuml.jar)
      -> render template Jinja2 (Markdown)
      -> export ke .docx lewat pypandoc.

Tidak menyentuh/menduplikasi logika Peran 1 (parser_service.py) atau
Peran 2 (llm_service.py) — modul ini murni konsumen dari Contract B.
"""

import base64
import copy
import io
import json
import re
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import docx
import pypandoc
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_ALIGN_VERTICAL, WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from jinja2 import Environment, FileSystemLoader
from PIL import Image, ImageChops, ImageDraw, UnidentifiedImageError

from app.core import config
from app.domain.exceptions import DiagramRenderError

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
OUTPUT_DIR = Path(tempfile.gettempdir()) / "auto_document_generator"
IMAGES_DIR = OUTPUT_DIR / "images"

# Template hasil-KOMPILASI upload user (V2): data/templates/<id>/ berisi manifest
# template.json, template Jinja per-doc_type (.md), dan reference.docx tersintesis.
# Persisten (bukan temp) — lihat config.TEMPLATES_STORE_PATH.
TEMPLATES_STORE = Path(config.TEMPLATES_STORE_PATH)

# autoescape=False karena output-nya Markdown, bukan HTML — auto-escaping
# justru akan merusak karakter Markdown biasa (*, _, |, dst).
_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)

# Registry template (sejak V1 multi-template, 2026-07-17): satu template = satu
# gaya dokumen, dipilih user lewat `template_id` di form. "default" = template
# yang dimodelkan dari acuan enterprise; "premco" = hasil KOMPILASI MANUAL docx
# PREMCO asli (V0/V1 roadmap tahap c — lihat scripts/validation/
# V0_TEMPLATE_PREMCO.md). Template boleh menyediakan sebagian jenis dokumen
# saja; kombinasi yang tidak tersedia ditolak ValueError -> 422 SINKRON di
# endpoint, sebelum ada kerja berbayar.
_TEMPLATE_REGISTRY: dict[str, dict[str, str]] = {
    "default": {
        "SDD": "sdd_template.md",
        "UAT": "uat_template.md",
    },
    "premco": {
        "SDD": "sdd_premco_template.md",
        "UAT": "uat_premco_template.md",
    },
}

# Template mana yang MEMAKAI diagram Component Integration di badan dokumennya.
# premco TIDAK (V0: dokumen aslinya cuma satu gambar arsitektur, tak ada bab
# Integrasi Komponen). Ini bukan sekadar hemat kerja: merender diagram yang tak
# dipakai membuat dokumen bisa GAGAL gara-gara diagram yang bahkan tak muncul —
# terbukti pada repo Nuxt MyPertamina.id, nama file dynamic-route `[slug].vue`
# masuk ke sintaks komponen PlantUML `[...]` lalu merusaknya, dan mematikan
# SELURUH generate premco. Diagram yang dipakai tetap gagal-berisik seperti dulu.
_TEMPLATES_USING_COMPONENT_INTEGRATION = {"default"}


def validate_template(template_id: str, document_type: str) -> None:
    """Tolak kombinasi template x jenis dokumen yang tidak tersedia — dipanggil
    SINKRON oleh endpoint (422 sebelum job dibuat) DAN oleh generate_docx
    (pertahanan kalau dipanggil dari jalur lain).

    Menerima built-in (`_TEMPLATE_REGISTRY`) DAN template hasil-kompilasi upload
    (V2, `data/templates/<id>/template.json`)."""
    normalized = document_type.upper()
    if template_id in _TEMPLATE_REGISTRY:
        doc_types = set(_TEMPLATE_REGISTRY[template_id])
    else:
        manifest = _load_compiled_manifest(template_id)
        if manifest is None:
            raise ValueError(
                f"template_id tidak dikenal: {template_id!r} "
                f"(tersedia: {', '.join(list_template_ids())})"
            )
        doc_types = set(manifest["doc_types"])
    if normalized not in doc_types:
        raise ValueError(
            f"Template {template_id!r} belum menyediakan dokumen "
            f"{normalized} (tersedia: {', '.join(sorted(doc_types))})."
        )

# Judul dokumen — masuk ke halaman pertama DAN ke kaki tiap halaman. Sengaja di
# sini, bukan sebagai `# Judul` di template: Pandoc merendernya dengan style
# `Title` (yang memang untuk itu) dan sekaligus menyimpannya ke docProps, tempat
# field TITLE di kaki halaman membacanya.
_TITLE_BY_DOC_TYPE = {
    "SDD": "Solution Design Document",
    "UAT": "Dokumen User Acceptance Testing (UAT)",
}

# Kerangka tampilan: font, gaya heading, dan kaki halaman bernomor. Dibangun oleh
# scripts/build_reference_docx.py — bukan file biner misterius.
REFERENCE_DOCX = TEMPLATES_DIR / "reference.docx"

# Perilaku per built-in yang TIDAK bisa dilihat dari nama template saja. Template
# hasil-kompilasi upload membawa flag ini di manifest-nya.
_BUILTIN_GROUPS_TEST_CASES = {"premco"}   # sisanya (default) pakai tabel test flat
_BUILTIN_UAT_TOC = {"default"}            # sisanya (premco) tanpa Daftar Isi
# Cover SDD di-align KANAN (blok judul + identitas), meniru cover PREMCO — atas
# permintaan pemilik (2026-07-21 lanjutan 11). Hanya premco; default tetap tengah.
_BUILTIN_COVER_ALIGN_RIGHT = {"premco"}


@dataclass(frozen=True)
class _ResolvedTemplate:
    """Semua yang dibutuhkan compiler untuk merender satu template — dari built-in
    ATAU dari template hasil-kompilasi upload. Satu tempat yang menyembunyikan
    perbedaan sumbernya."""
    template_id: str
    template: Any                     # jinja2.Template siap .render()
    reference_docx: Path
    uses_component_integration: bool  # render diagram Component Integration?
    groups_test_cases: bool           # UAT: kelompokkan test-case per modul?
    uat_toc: bool                     # UAT: pasang --toc?
    cover_align_right: bool           # SDD: ratakan kanan blok judul cover?


def _load_compiled_manifest(template_id: str) -> dict | None:
    """Manifest template hasil-kompilasi upload, atau None kalau bukan template
    terkompilasi (mis. built-in atau id tak dikenal)."""
    manifest = TEMPLATES_STORE / template_id / "template.json"
    if not manifest.exists():
        return None
    return json.loads(manifest.read_text(encoding="utf-8"))


def _compiled_template_ids() -> set[str]:
    if not TEMPLATES_STORE.exists():
        return set()
    return {p.name for p in TEMPLATES_STORE.iterdir()
            if (p / "template.json").exists()}


def list_template_ids() -> list[str]:
    """Semua template_id yang bisa dipakai: built-in + hasil-kompilasi upload.
    Publik: dipakai orkestrator kompilasi (cek keunikan id) & bisa dipakai
    frontend untuk mengisi dropdown gaya dokumen."""
    return sorted(set(_TEMPLATE_REGISTRY) | _compiled_template_ids())


def list_templates_detail() -> list[dict]:
    """Tiap template + `doc_types` yang tersedia + `source` + `name` — untuk
    dropdown gaya dokumen di frontend yang MENGHORMATI ketersediaan per jenis
    dokumen. Server jadi sumber kebenaran (dulu frontend hardcode daftarnya, dan
    `premco` UAT ketinggalan diam-diam ketika backend mulai mendukungnya)."""
    detail = []
    for tid in list_template_ids():
        if tid in _TEMPLATE_REGISTRY:
            detail.append({"id": tid, "name": tid, "source": "builtin",
                           "doc_types": sorted(_TEMPLATE_REGISTRY[tid])})
        else:
            manifest = _load_compiled_manifest(tid) or {}
            detail.append({"id": tid, "name": manifest.get("name", tid),
                           "source": "compiled",
                           "doc_types": sorted(manifest.get("doc_types", {}))})
    return detail


def _resolve_template(template_id: str, normalized_type: str) -> _ResolvedTemplate:
    """template_id + jenis dokumen → sumber Jinja + reference.docx + flag perilaku.
    Built-in muat dari app/templates/ + reference.docx ter-commit; template
    hasil-kompilasi upload muat dari data/templates/<id>/ + reference tersintesisnya
    sendiri. Prakondisi: kombinasi sudah lolos `validate_template`."""
    if template_id in _TEMPLATE_REGISTRY:
        name = _TEMPLATE_REGISTRY[template_id][normalized_type]
        return _ResolvedTemplate(
            template_id=template_id,
            template=_jinja_env.get_template(name),
            reference_docx=REFERENCE_DOCX,
            uses_component_integration=template_id in _TEMPLATES_USING_COMPONENT_INTEGRATION,
            groups_test_cases=template_id in _BUILTIN_GROUPS_TEST_CASES,
            uat_toc=template_id in _BUILTIN_UAT_TOC,
            cover_align_right=template_id in _BUILTIN_COVER_ALIGN_RIGHT,
        )
    manifest = _load_compiled_manifest(template_id)
    if manifest is None:
        raise ValueError(f"template_id tidak dikenal: {template_id!r} "
                         f"(tersedia: {', '.join(list_template_ids())})")
    base = TEMPLATES_STORE / template_id
    source = (base / manifest["doc_types"][normalized_type]).read_text(encoding="utf-8")
    return _ResolvedTemplate(
        template_id=template_id,
        template=_jinja_env.from_string(source),
        reference_docx=base / manifest["reference"],
        uses_component_integration=manifest.get("uses_component_integration", False),
        groups_test_cases=manifest.get("groups_test_cases", True),
        uat_toc=manifest.get("uat_toc", False),
        cover_align_right=manifest.get("cover_align_right", False),
    )

# Ketajaman render PlantUML. Default PlantUML 96 dpi — cukup untuk layar, buram
# untuk cetak (pelajaran yang sama dengan mermaid.ink dulu: layak cetak butuh
# ≥150 dpi, dan produk lama memakai ~246 dpi lewat width=1600). 300 dpi = tajam
# di kertas; membengkakkan PNG, tapi docx esteler tetap di kisaran ratusan KB.
_PLANTUML_DPI = 300

# PlantUML diam-diam MEMOTONG gambar yang melebihi 4096 px (default
# PLANTUML_LIMIT_SIZE) — pada 300 dpi, activity diagram yang panjang gampang
# menembusnya, dan hasilnya diagram terpenggal TANPA error. Batasnya dinaikkan
# lewat flag JVM (harus SEBELUM -jar).
_PLANTUML_LIMIT_SIZE = 16384

# Gaya visual diagram disuntik DI SINI, bukan ditulis LLM — filosofi yang sama
# dengan reference.docx: rupa dokumen diatur dari satu tempat yang deterministik,
# bukan dari output model yang bisa berubah-ubah antar panggilan.
#
# "TEMA ENTERPRISE" (Fase 1, 2026-07-22): menggantikan tampilan hitam-putih polos
# `!theme plain` yang membuat diagram terlihat seperti default PlantUML. Dipilih
# lewat Fase 0 — perbandingan berdampingan render esteler (PlantUML kini vs
# ber-tema vs D2, di scratchpad): tema ini uplift SERAGAM di ketiga tipe diagram
# (arsitektur/use case/activity) tanpa dependency baru & tanpa menyentuh pipeline
# AI, dan untuk use case + activity JUSTRU lebih baik daripada D2 (layout UML
# klasiknya lebih terbaca; D2 unggul hanya di graf-node arsitektur). Ikon vendor
# TIDAK ditambahkan: glyph generik redundan dengan bentuk (cylinder = database),
# dan logo vendor mustahil dicocokkan andal untuk service sembarang (cherry-pick).
#
# `!theme plain` TETAP jadi BASIS (menetralkan latar kuning default PlantUML untuk
# elemen yang tak kita warnai eksplisit); skinparam di bawahnya menimpanya. Palet:
# biru-abu korporat + aksen hangat (database) & ungu (cloud). Font SENGAJA tidak
# dipatok (mis. "Segoe UI" cuma ada di Windows; diagram dirender SERVER-SIDE) —
# biar konsisten lintas OS; uplift-nya datang dari warna/rounded/shadow, bukan font.
_PLANTUML_STYLE_PREAMBLE = (
    "!theme plain",
    f"skinparam dpi {_PLANTUML_DPI}",
    "skinparam backgroundColor #FFFFFF",
    "skinparam shadowing true",
    "skinparam roundcorner 12",
    "skinparam defaultFontSize 13",
    "skinparam ArrowColor #6B7A8D",
    "skinparam ArrowThickness 1.2",
    "skinparam ArrowFontColor #55636F",
    "skinparam componentStyle rectangle",
    "skinparam componentBackgroundColor #EEF4FB",
    "skinparam componentBorderColor #2E6BB0",
    "skinparam componentFontColor #17324D",
    "skinparam databaseBackgroundColor #FBEFE0",
    "skinparam databaseBorderColor #C87E22",
    "skinparam databaseFontColor #6B3F0B",
    "skinparam cloudBackgroundColor #F3EEF9",
    "skinparam cloudBorderColor #7A4FB0",
    "skinparam cloudFontColor #3A2560",
    "skinparam actorBackgroundColor #EAF2FA",
    "skinparam actorBorderColor #2E6BB0",
    "skinparam usecaseBackgroundColor #EEF4FB",
    "skinparam usecaseBorderColor #2E6BB0",
    "skinparam usecaseFontColor #17324D",
    "skinparam rectangleBackgroundColor #F8FAFC",
    "skinparam rectangleBorderColor #C2CDDA",
    "skinparam activityBackgroundColor #EEF4FB",
    "skinparam activityBorderColor #2E6BB0",
    "skinparam activityFontColor #17324D",
    "skinparam activityDiamondBackgroundColor #FBEFE0",
    "skinparam activityDiamondBorderColor #C87E22",
    "skinparam activityStartColor #2E6BB0",
    "skinparam activityEndColor #C0392B",
)

# Gaya POLOS — UML klasik hitam-putih, TANPA warna tema. Dipakai untuk tiga tipe
# diagram yang dokumen acuannya (PREMCO, digambar draw.io) memang hitam-putih:
# use case, activity, dan flow proses bisnis. Keputusan pemilik 2026-07-22:
# "use case, activity, dan flow proses bisnis tidak perlu tema supaya lebih mirip".
# Tema berwarna TETAP dipakai diagram arsitektur & integrasi komponen, yang di
# acuan memang bukan UML hitam-putih dan terbukti lebih terbaca dengan warna.
# `conditionStyle InsideDiamond` = keputusan digambar sebagai DIAMOND sungguhan
# dengan teks kondisi DI DALAMNYA dan label cabang di kiri-kanan — bentuk yang
# dipakai activity diagram draw.io acuan. Bawaan PlantUML menggambar heksagon
# dengan teks menempel di sisinya, yang tak pernah terbaca seperti flowchart.
# (Diprobe berdampingan: default vs `diamond` vs `InsideDiamond`; yang terakhir
# paling dekat ke acuan.) Hanya berpengaruh pada diagram activity.
_PLANTUML_PLAIN_PREAMBLE = ("!theme plain", f"skinparam dpi {_PLANTUML_DPI}",
                            "skinparam conditionStyle InsideDiamond")

# Bingkai penutup swimlane (lihat _close_swimlane_border): napas antara isi dan
# garis bingkai, dan tebal garisnya. Disamakan dengan tebal garis lane PlantUML
# supaya bingkai terbaca sebagai bagian diagram, bukan tempelan.
_SWIMLANE_BORDER_PAD = 10
_SWIMLANE_BORDER_WIDTH = 2
# Garis header lane dicari hanya di pita ATAS diagram. Kalau "celah sepi" baru
# ketemu lebih jauh dari ini, yang terdeteksi hampir pasti bukan baris judul —
# lebih baik tanpa garis header daripada memotong badan diagram.
_SWIMLANE_HEADER_MAX_FRAC = 0.25
# Paling banyak dua pita header: judul diagram, lalu baris nama lane.
_SWIMLANE_HEADER_MAX_LINES = 2

# Ruang yang benar-benar tersedia di halaman, dipakai _image_attr untuk membatasi
# ukuran tampil diagram. Lebar: 8,5 inci dikurangi margin 1 inci di dua sisi.
_PAGE_WIDTH_IN = 6.5

# Tinggi maksimum diagram. BUKAN sekadar "tinggi halaman dikurangi margin":
# gambar tidak pernah berjalan sendirian — judul sub-bab, kalimat pengantar, dan
# caption terikat padanya (keepNext, lihat _bind_lead_in_to_figure). Kalau
# batasnya dibiarkan setinggi mungkin, kelompok itu tak akan pernah muat di satu
# halaman, dan Word memindahkan SELURUHNYA — meninggalkan halaman yang isinya
# cuma sisa paragraf sebelumnya lalu 8 inci putih (terlihat di render esteler
# halaman 13: 4 baris teks, sisanya kosong). Jadi batas ini menyisakan ruang
# untuk rombongannya sendiri.
_TEXT_HEIGHT_IN = 9.0  # 11 inci - margin 1 inci atas & bawah
_FIGURE_GROUP_RESERVE_IN = 2.0  # judul sub-bab + pengantar + caption
_PAGE_HEIGHT_IN = _TEXT_HEIGHT_IN - _FIGURE_GROUP_RESERVE_IN

# Berapa piksel PNG per inci TAMPIL di dokumen — penentu ukuran teks di dalam
# diagram, dan teks itu harus seragam ANTAR diagram. 360 px/inci pada render 300
# dpi ≈ teks ~9pt di kertas (sedikit di bawah body 11pt, seperti diagram dokumen
# acuan). Menaikkan angka ini = teks lebih kecil & lebih tajam.
_DIAGRAM_DISPLAY_DPI = 360

# Lantai ukuran diagram (lihat _image_attr aturan 2 & 3). Diagram yang lebih
# kecil dari `TARGET_WIDTH_FRAC` x lebar area teks dibesarkan sampai menyentuhnya.
# 0,80 = tengah-tengah pita 75-90% yang diminta pemilik, dan masih di dalam pita
# 43-95% yang TERUKUR dari diagram dokumen acuan.
_DIAGRAM_TARGET_WIDTH_FRAC = 0.80

# Ketajaman minimum yang masih pantas dicetak (ambang yang sama dengan komentar
# _PLANTUML_DPI). Salah satu dari dua batas pembesaran, DITURUNKAN bukan ditebak:
# gambar dirender _PLANTUML_DPI dan ditampilkan pada _DIAGRAM_DISPLAY_DPI, jadi
# memperbesar n kali menurunkan kerapatan efektif jadi _PLANTUML_DPI/n.
_DIAGRAM_MIN_EFFECTIVE_DPI = 150

# Batas kedua, dan biasanya inilah yang menggigit: UKURAN TEKS DI DALAM DIAGRAM.
# Memperbesar gambar ikut memperbesar hurufnya, dan diagram berhuruf lebih besar
# dari teks badan terbaca seperti poster — tidak ada dokumen enterprise yang
# begitu (di PDF acuan teks diagram justru LEBIH KECIL dari teks badan).
#
# Ukuran alaminya dihitung, bukan ditebak: PlantUML memakai font 14 px pada 96
# dpi, dirender pada _PLANTUML_DPI, lalu ditampilkan pada _DIAGRAM_DISPLAY_DPI.
_DIAGRAM_NATURAL_TEXT_PT = 14 * (_PLANTUML_DPI / 96) / _DIAGRAM_DISPLAY_DPI * 72
# 12,5pt = sedikit di atas teks badan 11pt: cukup longgar supaya diagram boleh
# membesar, cukup ketat supaya tidak pernah terbaca sebagai poster.
_DIAGRAM_MAX_TEXT_PT = 12.5

# Konsekuensi yang DISENGAJA dari dua batas di atas: diagram yang secara
# struktur sederhana (use case 1 aktor 2 oval) TIDAK akan mencapai target lebar,
# karena lebar dan ukuran huruf terkunci satu sama lain — melebarkannya sampai
# 80% berarti hurufnya jadi 17pt. Diagram yang RUMIT (yang memang perlu ruang)
# mencapainya. Lantainya naik tanpa ada yang jadi poster.
_DIAGRAM_MAX_UPSCALE = min(
    _PLANTUML_DPI / _DIAGRAM_MIN_EFFECTIVE_DPI,
    _DIAGRAM_MAX_TEXT_PT / _DIAGRAM_NATURAL_TEXT_PT,
)

_MANUAL_PLACEHOLDER = "*(diisi manual)*"

# Bar judul tabel gaya PREMCO (baris pertama tabel di-merge jadi satu sel biru
# muda berjudul). Pipe table Markdown tidak bisa merge sel, jadi template
# menandai baris pertamanya dengan marker ini dan post-process yang mengubahnya
# jadi bar sungguhan. Warna birunya TERUKUR dari docx PREMCO asli (27 sel),
# bukan ditebak.
_TITLE_BAR_MARKER = "((BAR))"
_TITLE_BAR_FILL = "9CC3E5"

# Bar judul HITAM blok tanda tangan gaya PREMCO (Perwakilan User/Pengembang).
# Mekanisme sama dengan ((BAR)) biru — baris pertama tabel di-merge jadi satu bar
# berjudul — tapi latarnya HITAM dengan teks PUTIH, dan baris di bawahnya jadi
# ruang tanda tangan yang ditinggikan. Diukur dari docx PREMCO asli: bar fill
# 000000, tabel 3 baris × 2 kolom (bar, ruang tanda tangan, nama/jabatan).
_SIGNATURE_BAR_MARKER = "((SIGBAR))"
_SIGNATURE_BAR_FILL = "000000"
_WHITE_INK = "FFFFFF"

# Kolom "Entitas" tabel Tim Project cover gaya PREMCO di-merge VERTIKAL: satu
# nilai perusahaan memayungi seluruh baris tim. Pipe table Markdown tak bisa
# merge vertikal, jadi template menandai sel HEADER kolom itu dengan marker ini;
# post-process yang menggabung sel data kolom 0 (baris 1..N) jadi satu.
_COVER_MERGE_MARKER = "((CVMERGE))"

# Pemisah baris DI DALAM sel tabel. Markdown pipe table tidak bisa memuat baris
# baru, dan `<br/>` DIBUANG diam-diam oleh writer docx Pandoc (raw HTML tidak
# didukung di docx — terlihat di probe V1: langkah activity menyambung jadi
# "login.2. Admin ..."). Template menulis marker ini; post-process menukarnya
# dengan <w:br/> sungguhan.
_LINE_BREAK_MARKER = "((BR))"

# Header HIJAU tabel test-case gaya UAT PREMCO. Marker ini ditaruh di sel PERTAMA
# baris header oleh uat_premco_template.md; post-process mengubah baris header jadi
# hijau. Warna a8d08d TERUKUR dari header tabel test-case docx UAT asli — bukan
# ditebak. Header hitam bawaan reference (tblStylePr firstRow) dimatikan khusus
# tabel ini, karena teks putih di atas hijau muda kurang terbaca.
_GREEN_HEADER_MARKER = "((GH))"
_GREEN_HEADER_FILL = "a8d08d"

# Pemicu section LANDSCAPE. Tabel test-case UAT PREMCO ada di section landscape
# (diukur langsung dari docx asli: section 2 landscape, tabel 10,9 inci lebar) —
# 9 kolom mustahil muat rapi di potret. Template premco UAT menaruh marker ini
# sebagai paragraf tersendiri tepat sebelum Case Pengujian; post-process
# memecah section di situ dan memutar sisanya jadi landscape. Pandoc tidak punya
# konsep "section landscape sebagian", jadi ini satu-satunya tempat deterministik.
_LANDSCAPE_MARKER = "((LANDSCAPE))"

# Pasangan `((LANDSCAPE))`: mengembalikan orientasi ke potret. Tidak dibutuhkan
# premco UAT (di sana landscape memang sampai akhir dokumen), tapi WAJIB ada
# untuk template hasil-upload: template sembarang bisa punya satu bab landscape
# di TENGAH lalu kembali potret, dan tanpa penutup ini sisa dokumennya ikut
# terputar. Lihat _apply_orientation_markers.
_PORTRAIT_MARKER = "((PORTRAIT))"

# Blok cover yang TANPA kotak-kotak tabel. Keduanya tetap ditulis sebagai pipe
# table di template — itu satu-satunya cara Markdown menjamin kolom yang lurus —
# lalu post-process MELEPAS rupa tabelnya. Hasilnya: perataan seakurat tabel,
# tampilan setenang teks. Marker ditaruh di sel PERTAMA (pola yang sama dengan
# ((GH))), dan dibuang saat diproses.
#
#   ((CVBAND)) = pita identitas 3 kolom (Versi | RFC # | Classification):
#                tanpa garis sama sekali, label kecil-abu di atas nilai besar.
#   ((CVLIST)) = daftar label→nilai 2 kolom (kodifikasi, katalog, tim project):
#                cuma hairline antar-baris, tanpa bingkai luar.
_COVER_BAND_MARKER = "((CVBAND))"
_COVER_LIST_MARKER = "((CVLIST))"

# Abu-abu garis & teks sekunder cover. Nilainya SAMA dengan yang dipakai
# reference_synthesis_service (GRID / SEMIBOLD_INK); di-copy sebagai konstanta
# lokal karena compiler tidak boleh bergantung ke modul sintesis reference —
# reference.docx bisa datang dari template hasil upload (V2).
_COVER_RULE_INK = "BFBFBF"
_COVER_LABEL_INK = "595959"

# Logo di header: tinggi standar meniru logo dokumen acuan (~0,45 inci di kanan
# atas tiap halaman). Logo pita yang sangat lebar dibatasi LEBARNYA supaya tidak
# menabrak area teks — aturan yang sama dengan _image_attr: batasi sisi yang
# lebih dulu mentok.
_LOGO_HEIGHT_IN = 0.45
_LOGO_MAX_WIDTH_IN = 2.4

# Batas ukuran file logo. Logo perusahaan normal itu puluhan KB; 2 MB sudah
# sangat longgar, dan batasnya ada supaya field base64 di body JSON tidak bisa
# dipakai mengirim payload raksasa.
_LOGO_MAX_BYTES = 2 * 1024 * 1024


def decode_logo(logo_base64: str) -> bytes:
    """Base64 dari form -> bytes gambar yang SUDAH tervalidasi.

    Dipanggil endpoint secara SINKRON saat POST diterima: logo yang rusak harus
    ditolak 422 detik itu juga — bukan jadi job yang gagal tiga menit kemudian
    SETELAH membayar LLM. Prinsip yang sama dengan validasi document_type.

    Pillow yang memvalidasi isinya, bukan tebakan ekstensi/mime dari klien —
    pelajaran lama repo ini: header JPEG yang dibaca sebagai PNG menghasilkan
    angka ngawur tanpa error.
    """
    payload = logo_base64.strip()
    # FileReader.readAsDataURL di browser menghasilkan "data:image/png;base64,..."
    # — buang prefiksnya kalau ada, supaya frontend tidak wajib membersihkannya.
    if payload.startswith("data:"):
        _, _, payload = payload.partition(",")
    try:
        # binascii.Error (yang dilempar b64decode) adalah subclass ValueError.
        raw = base64.b64decode(payload, validate=True)
    except ValueError as e:
        raise ValueError("Logo bukan base64 yang valid.") from e
    if len(raw) > _LOGO_MAX_BYTES:
        raise ValueError(
            f"Logo terlalu besar ({len(raw) / 1024 / 1024:.1f} MB) — maksimum 2 MB."
        )
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError("Logo bukan file gambar yang dikenali (pakai PNG atau JPEG).") from e
    return raw


class _MetadataDict(dict):
    """dict yang mengembalikan penanda *(diisi manual)* untuk field yang tidak
    diisi pengguna.

    Alasan pakai __missing__ ketimbang daftar field eksplisit: daftar itu harus
    disinkronkan manual dengan DocumentMetadata di layer API, dan compiler tidak
    boleh mengimpor ke atas ke layer API. Dengan cara ini menambah field metadata
    cuma menyentuh schema + template — tidak ada daftar ketiga yang bisa basi.
    """

    def __missing__(self, key: str) -> str:
        return _MANUAL_PLACEHOLDER


def _build_metadata_context(document_metadata: dict[str, Any] | None) -> _MetadataDict:
    """Ambil field yang benar-benar diisi; sisanya biar __missing__ yang jawab.

    String kosong/spasi diperlakukan sama dengan tidak diisi — input form yang
    dikosongkan pengguna tidak boleh menghasilkan sel tabel kosong melompong.
    """
    filled = {
        key: value.strip()
        for key, value in (document_metadata or {}).items()
        if isinstance(value, str) and value.strip()
    }
    return _MetadataDict(filled)


def _strip_code_fence(diagram_script: str) -> str:
    """Buang code fence Markdown (```plantuml ... ```) kalau LLM terlanjur
    menyertakannya — fence bukan bagian bahasa diagram mana pun."""
    script = diagram_script.strip()
    if not script.startswith("```"):
        return script
    lines = [ln for ln in script.splitlines() if not ln.strip().startswith("```")]
    return "\n".join(lines).strip()


# Nuxt/Next menamai file dynamic-route dengan kurung siku: [id].vue, [...slug].vue,
# [[...all]].vue. Nama itu masuk ke diagram sebagai [product/[category]/[slug].vue],
# dan kurung siku BERSARANG merusak sintaks komponen PlantUML [...] → seluruh
# dokumen gagal (ditemukan pada MyPertamina.id-Clone, 2026-07-18). Cocokkan HANYA
# segmen route-param (isinya identifier: [\w-], boleh diawali "..."); nama komponen
# ber-titik seperti [login.vue] dan token PlantUML khusus [*]/[H] TIDAK tersentuh
# karena isinya bukan identifier murni.
#
# Dua bentuk, dicocokkan BERIMBANG (kurung buka = tutup): single `[id]`/`[...slug]`
# dan double `[[id]]`/`[[...all]]` (optional route Nuxt). Double dicocokkan DULU —
# kalau tidak, `[[type]/...]` (kurung KOMPONEN + param single yang jadi segmen
# pertama) salah dibaca `\[\[?...\]?` sebagai optional-catch-all lalu MEMAKAN kurung
# komponennya. Bug itu lolos dari MyPertamina (paramnya tak pernah segmen pertama)
# tapi tertangkap nuxt/movies (`pages/[type]/...` → label diawali `[[type]`).
_ROUTE_PARAMS = (
    r"\[\[\.{0,3}([\w-]+)\]\]",   # double: [[id]] [[...all]]
    r"\[\.{0,3}([\w-]+)\]",       # single: [id] [...slug]
)
_TOKEN_GLUE = r"[\w/.]"  # bukti bahwa kurung ini BAGIAN nama file, bukan komponen berdiri sendiri (spasi/`as` = komponen)


def _sanitize_route_param_brackets(script: str) -> str:
    """Lepas kurung siku route-param Nuxt/Next yang terjepit di dalam nama file
    (mis. `[slug]` di `pages/[slug].vue`) supaya tidak merusak sintaks `[...]`
    PlantUML. Diagram TETAP dirender (nama file jadi `pages/slug.vue`), bukan
    diganti placeholder — isinya utuh, cuma kurungnya dilepas."""
    previous = None
    while previous != script:
        previous = script
        for pattern in _ROUTE_PARAMS:
            script = re.sub(rf"(?<={_TOKEN_GLUE}){pattern}", r"\1", script)
            script = re.sub(rf"{pattern}(?={_TOKEN_GLUE})", r"\1", script)
    return script


# Subjek kalimat yang menandai satu langkah dikerjakan SISTEM (bukan aktor).
# Dipakai `_add_swimlanes` untuk menebak lane tiap langkah.
_SYSTEM_SUBJECTS = ("sistem", "aplikasi", "server", "backend", "api", "service",
                    "layanan", "database", "chatbot")
# Kata pembuka yang menandai langkah dikerjakan MANUSIA, kalau nama aktornya
# sendiri tidak muncul di awal kalimat.
_ACTOR_SUBJECTS = ("user", "pengguna", "admin", "customer", "pelanggan", "kasir",
                   "staf", "petugas", "operator")
_ACTIVITY_ACTION = re.compile(r"^(\s*):(.+);\s*$")   # baris aksi `:Langkah;`
_EXISTING_LANE = re.compile(r"^\s*\|[^|]*\|\s*$")    # baris `|Lane|` yang sudah ada


def _lane_for_step(text: str, actor_lane: str, system_lane: str) -> str | None:
    """Lane untuk satu langkah activity, atau None kalau SUBJEKNYA TIDAK JELAS.

    None berarti "warisi lane berjalan" — sengaja, bukan malas: menebak lane untuk
    kalimat tanpa subjek jelas ("Validasi data") lebih berbahaya daripada
    membiarkannya di lane sebelumnya, karena lane yang SALAH menyatakan tanggung
    jawab yang salah — dan itu kesalahan isi, bukan sekadar rupa.
    """
    lowered = text.strip().lower()
    if any(lowered.startswith(word) for word in _SYSTEM_SUBJECTS):
        return system_lane
    first_word = actor_lane.strip().lower().split()[0] if actor_lane.strip() else ""
    if first_word and lowered.startswith(first_word):
        return actor_lane
    if any(lowered.startswith(word) for word in _ACTOR_SUBJECTS):
        return actor_lane
    return None


def _has_swimlanes(diagram_script: str) -> bool:
    """Apakah script sudah memuat baris lane `|Nama|`? Dipakai untuk memutuskan
    apakah diagram perlu dibingkai — lane bisa datang dari LLM ATAU dari
    `_add_swimlanes`, dan keduanya sama-sama butuh bingkai penutup."""
    return any(_EXISTING_LANE.match(line) for line in diagram_script.splitlines())


def _add_swimlanes(diagram_script: str, actor: str | None) -> str:
    """Sisipkan swimlane `|Aktor|`/`|Sistem|` ke PlantUML ACTIVITY dari LLM.

    Kenapa di sini dan bukan di prompt: dokumen acuan (PREMCO, dibuat draw.io)
    memakai swimlane User|Sistem, dan itulah ciri utama "activity diagram yang
    baik" menurut pemilik. PlantUML mendukungnya native — yang kurang cuma
    INFORMASI siapa mengerjakan apa. Ternyata informasi itu SUDAH ada: prompt
    llm_service mewajibkan tiap langkah difrasakan "Aktor melakukan X" /
    "Sistem merespons Y", jadi subjeknya selalu di awal kalimat dan bisa dibaca
    tanpa menyentuh pipeline AI sama sekali. Diukur pada 8 diagram esteler nyata:
    8/8 render sukses, NOL langkah ambigu.

    Konservatif — dikembalikan APA ADANYA kalau:
      * script sudah punya lane (LLM/temp lain sudah mengaturnya), atau
      * bukan activity beta (tak ada baris `:Langkah;`) — jadi diagram
        arsitektur/komponen/use case tak mungkin tersentuh.
    Lane hanya ditulis saat BERUBAH (PlantUML mewariskan lane berjalan).
    """
    actor_lane = (actor or "User").strip() or "User"
    system_lane = "Sistem"
    if actor_lane.lower() == system_lane.lower():
        actor_lane = "User"

    lines = diagram_script.splitlines()
    if _has_swimlanes(diagram_script):
        return diagram_script
    if not any(_ACTIVITY_ACTION.match(line) for line in lines):
        return diagram_script

    out: list[str] = []
    current: str | None = None
    for line in lines:
        match = _ACTIVITY_ACTION.match(line)
        if match:
            indent, text = match.group(1), match.group(2)
            lane = _lane_for_step(text, actor_lane, system_lane)
            if lane is not None and lane != current:
                out.append(f"{indent}|{lane}|")
                current = lane
        elif line.strip() == "start" and current is None:
            # Alur activity selalu dimulai dari sisi manusia di dokumen acuan.
            out.append(f"|{actor_lane}|")
            current = actor_lane
        out.append(line)
    return "\n".join(out)


def _swimlane_header_bottoms(image, content_top: int) -> list[int]:
    """Cari batas bawah pita-pita HEADER di atas diagram swimlane.

    Membaca "tinta per baris": pita berteks (judul diagram, lalu nama lane) berisi
    banyak piksel gelap, dan di antaranya ada CELAH yang isinya cuma garis lane
    vertikal (tinta sangat sedikit). Tiap peralihan berteks -> sepi = satu batas.

    Kembalikan sampai `_SWIMLANE_HEADER_MAX_LINES` batas, urut dari atas:
      * dengan `title` -> 2 batas (bawah judul, bawah baris nama lane)
      * tanpa `title`  -> 1 batas (bawah baris nama lane)
    Dibatasi `_SWIMLANE_HEADER_MAX_FRAC` tinggi diagram: di luar itu yang
    terdeteksi hampir pasti badan diagram, dan menggambar garis di situ akan
    memotongnya.
    """
    grey = image.convert("L")
    width, height = grey.size
    pixels = grey.load()
    quiet = max(6, int(0.01 * width))     # ambang "cuma garis lane vertikal"
    limit = min(height, content_top + int(height * _SWIMLANE_HEADER_MAX_FRAC))
    bottoms: list[int] = []
    seen_text = False
    for y in range(content_top, limit):
        ink = sum(1 for x in range(width) if pixels[x, y] < 200)
        if ink > quiet:
            seen_text = True
        elif seen_text:
            bottoms.append(y)
            seen_text = False
            if len(bottoms) >= _SWIMLANE_HEADER_MAX_LINES:
                break
    return bottoms


def _close_swimlane_border(image_path: str) -> None:
    """Bingkai diagram swimlane jadi TABEL: kotak penutup + garis di bawah baris
    judul lane.

    Dua cacat yang ditutup, keduanya dikeluhkan pemilik. (1) PlantUML menggambar
    swimlane hanya sebagai garis VERTIKAL — tak ada garis atas & bawah, jadi
    kotaknya menganga; tidak ada skinparam untuk menutupnya (dua varian diprobe,
    hasilnya identik). (2) Baris judul lane cuma teks mengambang, sehingga tidak
    terbaca sebagai header tabel; acuan draw.io memisahkannya dengan garis.

    Hasilnya: kolom kiri = lajur aktor, kolom kanan = lajur Sistem, dengan header
    ber-garis — "tabel sebagai latar, alur menyesuaikan lajurnya".

    Digambar sesudah PNG jadi — pola yang sama dengan post-process docx: yang tak
    bisa diminta ke generator, direbut setelah hasilnya ada. Bingkai ditarik pada
    kotak-batas ISI + sedikit napas, jadi menempel pada ujung garis lane.
    """
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        content = ImageChops.difference(
            rgb, Image.new("RGB", rgb.size, (255, 255, 255))
        ).getbbox()
        if content is None:          # diagram kosong — tak ada yang dibingkai
            return
        header_bottoms = _swimlane_header_bottoms(rgb, content[1])
        pad = _SWIMLANE_BORDER_PAD
        canvas = Image.new("RGB", (rgb.width + 2 * pad, rgb.height + 2 * pad), "white")
        canvas.paste(rgb, (pad, pad))
        left, top, right, bottom = content
        pen = ImageDraw.Draw(canvas)
        pen.rectangle([left, top, right + 2 * pad, bottom + 2 * pad],
                      outline=(0, 0, 0), width=_SWIMLANE_BORDER_WIDTH)
        for y in header_bottoms:
            pen.line([left, y + pad, right + 2 * pad, y + pad],
                     fill=(0, 0, 0), width=_SWIMLANE_BORDER_WIDTH)
        canvas.save(image_path)


def _add_diagram_title(diagram_script: str, title: str | None) -> str:
    """Sisipkan `title` PlantUML sesudah `@startuml`, kalau belum ada.

    Judul dirender di ATAS diagram — dan karena bingkai swimlane ditarik pada
    kotak-batas ISI, judul itu ikut TERKURUNG di dalam kotak, tepat di atas baris
    nama lane. Hasilnya pita judul seperti activity diagram draw.io acuan
    ("Login Premco Website" membentang di atas kolom User|Sistem)."""
    if not title or not title.strip():
        return diagram_script
    if any(line.strip().lower().startswith("title ")
           for line in diagram_script.splitlines()):
        return diagram_script            # LLM sudah menulis judul sendiri
    out, injected = [], False
    for line in diagram_script.splitlines():
        out.append(line)
        if not injected and line.strip().startswith("@startuml"):
            out.append(f"title {title.strip()}")
            injected = True
    return "\n".join(out)


def _render_activity_diagram(diagram_script: str, images_dir: Path,
                             actor: str | None = None,
                             title: str | None = None) -> str:
    """Render diagram ACTIVITY: gaya POLOS (hitam-putih) + swimlane + bingkai
    penutup. Jatuh kembali ke versi TANPA lane kalau versi ber-lane gagal.

    Fallback sempit ini disengaja (bukan `except` lebar yang meratakan sebab —
    prinsip #3): swimlane itu peningkatan RUPA, dan rupa tidak boleh sanggup
    menggagalkan seluruh dokumen. Presedennya nyata — kurung route-param Nuxt
    pernah mematikan SELURUH generate premco lewat satu diagram. Kalau script
    aslinya sendiri yang rusak, error tetap muncul dari percobaan kedua.
    """
    script = _add_diagram_title(_add_swimlanes(diagram_script, actor), title)
    try:
        path = _render_diagram_to_image(script, images_dir, _PLANTUML_PLAIN_PREAMBLE)
    except DiagramRenderError:
        if script == diagram_script:
            raise            # bukan sisipan kita yang merusak — script aslinya rusak
        path = _render_diagram_to_image(diagram_script, images_dir,
                                        _PLANTUML_PLAIN_PREAMBLE)
        script = diagram_script
    # Dibingkai kalau hasil AKHIR punya lane — entah lane itu ditulis LLM sendiri
    # atau disisipkan `_add_swimlanes`. (Dulu keliru: cuma dibingkai kalau KITA
    # yang menambah, sehingga lane tulisan LLM lolos tanpa bingkai.)
    if _has_swimlanes(script):
        _close_swimlane_border(path)
    return path


def _normalize_plantuml(diagram_script: str,
                        style: tuple[str, ...] = _PLANTUML_STYLE_PREAMBLE) -> str:
    """Siapkan script LLM untuk plantuml.jar: buang fence, lepas kurung siku
    route-param yang merusak sintaks, pastikan terbungkus @startuml/@enduml, lalu
    suntik preamble gaya (theme + dpi) TEPAT sesudah @startuml.

    Preamble disuntik di sini dan LLM DILARANG menulis theme/skinparam sendiri
    (lihat SYSTEM_PROMPT llm_service): rupa diagram harus datang dari satu tempat
    deterministik, bukan dari selera model yang berubah antar panggilan — filosofi
    yang sama dengan reference.docx untuk rupa dokumen.
    """
    script = _sanitize_route_param_brackets(_strip_code_fence(diagram_script))
    if "@startuml" not in script:
        script = f"@startuml\n{script}\n@enduml"

    lines = []
    injected = False
    for line in script.splitlines():
        lines.append(line)
        if not injected and line.strip().startswith("@startuml"):
            lines.extend(style)
            injected = True
    return "\n".join(lines)


def _run_plantuml(plantuml_source: str) -> bytes:
    """Jalankan plantuml.jar (mode -pipe: source di stdin, PNG di stdout).

    Dipisah dari _render_diagram_to_image supaya test bisa me-mock PROSES
    EKSTERNALNYA saja — normalisasi script dan penulisan file tetap teruji asli.

    Render LOKAL, bukan layanan hosted — dua alasan, satu keputusan (2026-07-16):
    (1) privasi: isi diagram (nama endpoint, struktur komponen) tidak lagi
    meninggalkan mesin — keterbatasan mermaid.ink yang tercatat sejak awal;
    (2) rupa: PlantUML menggambar UML sungguhan (aktor stick-figure, oval use
    case, start/stop activity) — bahasa visual dokumen acuan enterprise, dipilih
    pemilik project lewat perbandingan berdampingan (scripts/diagram_comparison.py).

    -Playout=smetana: layout engine Java murni bawaan jar. Tanpa ini diagram
    use case & component menuntut Graphviz/dot terpasang terpisah di sistem —
    dependency kedua yang diam-diam, gagal hanya di mesin yang tidak punya.
    """
    jar = Path(config.PLANTUML_JAR)
    if not jar.is_file():
        raise DiagramRenderError(
            f"plantuml.jar tidak ditemukan di '{jar}'. Unduh dari "
            f"https://github.com/plantuml/plantuml/releases (asset "
            f"plantuml-<versi>.jar), simpan sebagai tools/plantuml.jar, atau "
            f"tunjuk lokasinya lewat PLANTUML_JAR di .env."
        )

    try:
        result = subprocess.run(
            ["java", f"-DPLANTUML_LIMIT_SIZE={_PLANTUML_LIMIT_SIZE}",
             "-jar", str(jar), "-pipe", "-tpng",
             "-charset", "UTF-8", "-Playout=smetana"],
            input=plantuml_source.encode("utf-8"),
            capture_output=True,
            timeout=120,
        )
    except FileNotFoundError as e:
        raise DiagramRenderError(
            "Java tidak ditemukan di PATH — render diagram PlantUML butuh "
            "Java 17+ terpasang."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise DiagramRenderError(
            "PlantUML tidak selesai merender dalam 120 detik — script diagram "
            "kemungkinan terlalu besar."
        ) from e

    # PlantUML MENGGAMBAR pesan syntax error sebagai gambar (exit code tetap
    # non-nol) — kalau cuma percaya stdout, error itu ter-embed diam-diam ke
    # dokumen sebagai "diagram". Periksa exit code DAN magic number PNG.
    if result.returncode != 0 or not result.stdout.startswith(b"\x89PNG"):
        stderr = result.stderr.decode("utf-8", "replace").strip()
        raise DiagramRenderError(
            f"PlantUML menolak script diagram: {stderr[:400] or 'tanpa detail'} "
            f"(cek syntax PlantUML-nya)."
        )
    return result.stdout


def _render_diagram_to_image(diagram_script: str, images_dir: Path,
                             style: tuple[str, ...] = _PLANTUML_STYLE_PREAMBLE) -> str:
    """Render satu script PlantUML jadi file PNG lokal; kembalikan path-nya.

    `style` memilih preamble gaya: tema berwarna (default, untuk arsitektur &
    integrasi komponen) atau `_PLANTUML_PLAIN_PREAMBLE` (UML hitam-putih, untuk
    use case / activity / flow proses bisnis)."""
    images_dir.mkdir(parents=True, exist_ok=True)
    png = _run_plantuml(_normalize_plantuml(diagram_script, style))
    image_path = images_dir / f"{uuid.uuid4().hex}.png"
    image_path.write_bytes(png)
    return str(image_path)


def _image_attr(image_path: str) -> str:
    """Atribut ukuran Pandoc (`{width=...}` / `{height=...}`) untuk satu diagram.

    Tiga aturan, tiga cacat yang dicegah:

    1. JANGAN MELUBER. Diagram yang lebih besar dari area teks diciutkan di sisi
       yang lebih dulu mentok — diagram lebar dibatasi LEBARnya, diagram tinggi
       dibatasi TINGGInya, sisi satunya ikut proporsional jadi tak ada yang
       gepeng. (Kasus terukur pada esteler: 5 dari 11 diagram setinggi 9,7-17,2
       inci di halaman 11 inci.)
    2. JANGAN KEKECILAN. Diagram sederhana (use case 1 aktor 2 oval) keluar
       cuma 0,55 x 0,27 inci pada ukuran alaminya — terukur 42% lebar area teks
       dengan lautan putih di kiri-kanannya. Kalau masih di bawah
       `_DIAGRAM_TARGET_WIDTH_FRAC`, diagram DIBESARKAN sampai menyentuh target.
    3. JANGAN JADI POSTER, JANGAN BURAM. Pembesarannya dibatasi
       `_DIAGRAM_MAX_UPSCALE` — dua ambang terukur sekaligus: huruf di dalam
       diagram tak boleh melewati `_DIAGRAM_MAX_TEXT_PT`, dan kerapatan efektif
       tak boleh turun di bawah `_DIAGRAM_MIN_EFFECTIVE_DPI`. Konsekuensinya
       jujur: diagram yang secara STRUKTUR sederhana tidak akan mencapai target
       lebar — lebar dan ukuran huruf terkunci satu sama lain, dan huruf 17pt di
       dalam diagram lebih merusak daripada diagram yang 60% lebar.

    Aturan 2 sengaja TIDAK memaksa setiap diagram selebar halaman. Diukur dari
    PDF acuan (87 halaman, tiap gambar diukur): diagramnya sendiri memakai
    43-95% lebar area teks — mayoritas activity diagram justru 43-54%. Yang
    membuat diagram acuan terlihat berwibawa bukan lebarnya, melainkan tidak
    adanya diagram MUNGIL. Target di sini menaikkan lantai, bukan menyamaratakan.

    Pillow, bukan parsing header PNG manual: JPEG yang dibaca sebagai PNG
    menghasilkan angka ngawur TANPA error (65536 x 4293001688 — betulan terjadi
    di sesi ini). Pillow memvalidasi formatnya dan gagal berisik.
    """
    with Image.open(image_path) as image:
        width, height = image.size
    natural_width_in = width / _DIAGRAM_DISPLAY_DPI
    natural_height_in = height / _DIAGRAM_DISPLAY_DPI

    # Terlalu besar -> ciutkan di sisi yang lebih dulu mentok.
    if natural_width_in > _PAGE_WIDTH_IN or natural_height_in > _PAGE_HEIGHT_IN:
        if height / width > _PAGE_HEIGHT_IN / _PAGE_WIDTH_IN:
            return f"{{height={_PAGE_HEIGHT_IN}in}}"
        return f"{{width={_PAGE_WIDTH_IN}in}}"

    # Terlalu kecil -> besarkan sampai target, dibatasi ketajaman DAN tinggi
    # halaman (diagram jangkung tak boleh terdorong keluar halaman oleh aturan
    # lebar).
    target_width_in = _PAGE_WIDTH_IN * _DIAGRAM_TARGET_WIDTH_FRAC
    scale = min(
        target_width_in / natural_width_in,
        _PAGE_HEIGHT_IN / natural_height_in,
        _DIAGRAM_MAX_UPSCALE,
    )
    if scale <= 1:
        return f"{{width={natural_width_in:.2f}in}}"
    return f"{{width={natural_width_in * scale:.2f}in}}"


def _build_sdd_context(data: dict[str, Any], render_integration: bool = True) -> dict[str, Any]:
    diagrams = data["diagrams"]

    # Ganti newline jadi spasi supaya tidak merusak baris tabel Markdown
    # (satu baris tabel Markdown wajib satu baris teks) — sama seperti
    # penanganan uat_test_cases di _build_uat_context.
    cleaned_features = [
        {**feature, "description": feature["description"].replace("\n", " ")}
        for feature in data.get("feature_requirements", [])
    ]
    cleaned_use_cases = [
        {
            **uc,
            "description": uc["description"].replace("\n", " "),
            "pre_condition": uc["pre_condition"].replace("\n", " "),
            "acceptance_criteria": [ac.replace("\n", " ") for ac in uc.get("acceptance_criteria", [])],
        }
        for uc in data.get("use_cases", [])
    ]
    cleaned_roles = [
        {**role, "description": role["description"].replace("\n", " ")}
        for role in data.get("user_roles", [])
    ]
    cleaned_requirements = [
        {**req, "detail": req["detail"].replace("\n", " ")}
        for req in data.get("system_requirements", [])
    ]
    cleaned_flow_steps = [step.replace("\n", " ") for step in data.get("business_flow_steps", [])]

    # Diagram yang DIPAKAI template diakses dengan diagrams[...] — sengaja KeyError
    # kalau hilang: dokumen tanpa salah satunya cacat, dan lebih baik gagal berisik.
    # component_integration cuma dirender kalau template memakainya (premco tidak),
    # jadi diagram yang tak dipakai tidak pernah menggagalkan generate.
    architecture = _render_diagram_to_image(diagrams["system_architecture"], IMAGES_DIR)
    integration = (
        _render_diagram_to_image(diagrams["component_integration"], IMAGES_DIR)
        if render_integration
        else None
    )
    # Flow proses bisnis SENGAJA tanpa swimlane (keputusan pemilik 2026-07-22):
    # di dokumen acuan ia berbentuk FLOWCHART bercabang, bukan diagram berlajur
    # seperti activity per-fitur — "jangan pakai template yang sama dengan
    # activity diagram". Gaya polos hitam-putih, sama dengan use case & activity.
    business_flow = _render_diagram_to_image(diagrams["business_process_flow"],
                                             IMAGES_DIR, _PLANTUML_PLAIN_PREAMBLE)
    # Use case: SATU diagram gabungan (semua aktor dalam satu gambar), sesuai gaya
    # dokumen UML acuan. Untuk dokumen dengan sangat banyak aktor+use case yang
    # dipakai bersama, panah bisa menyilang — itu batas struktural diagram
    # gabungan (layout smetana/dot/elk sama saja; diukur 2026-07-20), bukan bug.
    use_case = _render_diagram_to_image(diagrams["use_case_diagram"], IMAGES_DIR,
                                        _PLANTUML_PLAIN_PREAMBLE)

    return {
        **data,
        "feature_requirements": cleaned_features,
        "use_cases": cleaned_use_cases,
        "user_roles": cleaned_roles,
        "system_requirements": cleaned_requirements,
        "business_flow_steps": cleaned_flow_steps,
        "diagrams": {
            "system_architecture_image": architecture,
            "system_architecture_attr": _image_attr(architecture),
            "component_integration_image": integration,
            "component_integration_attr": _image_attr(integration) if integration else "",
            "business_process_flow_image": business_flow,
            "business_process_flow_attr": _image_attr(business_flow),
            "use_case_diagram_image": use_case,
            "use_case_diagram_attr": _image_attr(use_case),
            "activity_diagrams": [
                {
                    "activity_name": activity["activity_name"],
                    "description": activity["description"],
                    "actor": activity["actor"].replace("\n", " "),
                    "pre_condition": activity["pre_condition"].replace("\n", " "),
                    "steps": [s.replace("\n", " ") for s in activity["steps"]],
                    "image_path": path,
                    "image_attr": _image_attr(path),
                }
                for activity, path in (
                    # `actor` jadi NAMA lane manusianya; `activity_name` jadi pita
                    # judul di dalam kotak (meniru activity diagram draw.io acuan).
                    (a, _render_activity_diagram(a["diagram_script"], IMAGES_DIR,
                                                 a.get("actor"), a.get("activity_name")))
                    for a in diagrams.get("activity_diagrams", [])
                )
            ],
        },
    }


def _document_title(normalized_type: str, project_name: str) -> str:
    """Judul dokumen: dipakai DUA kali oleh Word — sebagai judul besar di halaman
    pertama (style `Title`), dan sebagai teks di kaki SETIAP halaman (field
    `TITLE` di reference.docx membacanya dari docProps). Satu sumber, dua tempat.

    Meniru acuan, yang menaruh judul yang sama di kedua tempat itu."""
    label = _TITLE_BY_DOC_TYPE[normalized_type]
    return f"{label} — {project_name}" if project_name.strip() else label


def _pandoc_args(normalized_type: str, title: str, reference_docx: Path = REFERENCE_DOCX,
                 uat_toc: bool = True) -> list[str]:
    """Argumen Pandoc per jenis dokumen.

    `--reference-doc` membawa TAMPILAN: font, gaya heading, dan yang paling
    penting **kaki halaman berisi nomor halaman**. Kerangka bawaan Pandoc tidak
    punya footer sama sekali (diperiksa langsung), dan itu bukan cuma soal rupa:
    Daftar Gambar menulis "Gambar 4 ... 14" sementara tidak ada halaman yang
    bertuliskan "14", jadi pembaca harus menghitung dari depan. Indeksnya tidak
    bisa dipakai. Lihat `scripts/build_reference_docx.py`.

    SDD sengaja TANPA `--toc`/`--lof`/`--lot` (sejak 2026-07-16): Pandoc memaku
    posisi ketiga daftar itu TEPAT sesudah judul — sebelum body — sehingga
    Daftar Isi mendarat di halaman cover, sementara dokumen acuan menaruh cover +
    identitas + revisi + persetujuan DULU dan daftar-daftar menyusul di halaman
    5-7. Field TOC yang sama persis (`TOC \\o "1-3" \\h \\z \\u`, `TOC \\h \\z
    \\t "Image Caption" \\c`, dst) kini ditanam langsung di sdd_template.md pada
    posisi yang benar, dan Word tetap mengisinya saat dibuka karena
    `updateFields` dibawa reference.docx (diprobe: Pandoc menyalin settings.xml
    dari reference doc). WORD yang menghitung nomor halamannya — kita tetap
    tidak perlu tahu pagination dari sisi Markdown.

    UAT `default` memakai `--toc` + `toc-title`: urutan halamannya belum jadi
    target, dan `--lof`/`--lot` memang tidak boleh ada di sana — UAT punya NOL
    gambar, dua daftar itu cuma jadi halaman indeks kosong. UAT `premco` justru
    TANPA `--toc`: dokumen UAT PREMCO asli tidak punya Daftar Isi sama sekali
    (diukur langsung — nol field TOC), dan template-nya pun flat tanpa heading,
    jadi Daftar Isi malah kosong.

    `lang=id` dipertahankan untuk locale dokumen; `--columns=20` menurunkan
    ambang "baris tabel dianggap panjang" sehingga SEMUA pipe table template
    memakai LEBAR KOLOM PROPORSIONAL dari rasio dash di separator row
    (diprobe: 5:8:32 dash → 880:1408:5632 twip). Tanpa itu tabel pendek jatuh ke
    autofit Word, dan kolom yang selnya kosong (Nama di Tim & Peran, No
    Kodifikasi) MENYUSUT sampai sepersekian sentimeter — terlihat di probe.
    Ambangnya 20, bukan 30: baris terpendek yang masih perlu rasio ("| Business
    IT Solution | |") cuma 26 karakter.
    """
    args = [
        "--standalone",
        "--columns=20",
        "-M",
        "lang=id",
        "-M",
        f"title={title}",
        f"--reference-doc={reference_docx}",
    ]
    if normalized_type == "UAT" and uat_toc:
        args += ["--toc", "-M", "toc-title=Daftar Isi"]
    return args


def _merge_first_row_into_bar(table, fill: str, white_text: bool) -> None:
    """Gabung SELURUH sel baris pertama tabel jadi satu BAR judul berwarna: sel
    tunggal selebar tabel, teks bold di tengah, latar `fill`.

    Dipakai dua bar gaya PREMCO yang beda warna: ((BAR)) biru (use case/activity,
    teks gelap) dan ((SIGBAR)) hitam (blok tanda tangan, teks putih). Conditional
    formatting `firstRow` table style (header hitam) DIMATIKAN dulu — kalau tidak,
    warna bar tertimpa hitam bawaan dan teksnya jadi putih-di-atas-warna.
    """
    first_row = table.rows[0]
    title = first_row.cells[0].text.strip()

    _disable_conditional_header(table)

    merged = first_row.cells[0]
    for cell in first_row.cells[1:]:
        merged = merged.merge(cell)
    # `merged.text = ...` membuang paragraf sel BESERTA style-nya (jadi Normal,
    # bukan Compact seperti sel tabel lain) — bar judul jadi berhuruf 11pt di
    # antara isi 10,5pt dan berspasi beda. Yang diganti cukup teksnya; paragraf
    # pertama dipertahankan.
    paragraph = merged.paragraphs[0]
    for extra in merged.paragraphs[1:]:
        extra._p.getparent().remove(extra._p)
    for extra_run in paragraph.runs[1:]:
        extra_run._r.getparent().remove(extra_run._r)
    if paragraph.runs:
        paragraph.runs[0].text = title
    else:
        paragraph.add_run(title)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in paragraph.runs:
        run.bold = True
        if white_text:
            run.font.color.rgb = RGBColor.from_string(_WHITE_INK)
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), fill)
    merged._tc.get_or_add_tcPr().append(shading)


def _keep_table_together(table) -> None:
    """Ikat semua baris kecuali yang terakhir (keepNext) supaya tabel UTUH pindah
    halaman — tanpa ini tabel kecil gampang patah tepat sesudah barisnya, dan bar
    header (yang juga tblHeader) terulang membingungkan (terlihat di probe V1)."""
    rows = list(table.rows)
    for row in rows[:-1]:
        for cell in row.cells:
            for cell_paragraph in cell.paragraphs:
                _set_keep_next(cell_paragraph._p)


def _apply_title_bars(document) -> None:
    """Ubah baris pertama tabel yang ditandai _TITLE_BAR_MARKER jadi BAR JUDUL
    gaya PREMCO: satu sel merged selebar tabel, latar biru muda, teks bold di
    tengah — persis tabel use case/activity di docx PREMCO asli.

    Kenapa post-process: pipe table Markdown tidak punya sintaks merge sel, dan
    conditional formatting `firstRow` dari table style (header hitam-teks-putih)
    harus DIMATIKAN khusus untuk tabel ber-bar — teks putih di atas biru muda
    tidak terbaca. Keduanya cuma bisa dilakukan sesudah docx jadi.
    """
    for table in document.tables:
        if _take_table_marker(table, _TITLE_BAR_MARKER) is None:
            continue
        _merge_first_row_into_bar(table, _TITLE_BAR_FILL, white_text=False)
        _keep_table_together(table)


def _apply_signature_bars(document) -> None:
    """Ubah tabel bertanda _SIGNATURE_BAR_MARKER jadi blok tanda tangan gaya
    PREMCO: bar judul HITAM (teks putih) selebar tabel, lalu ruang tanda tangan
    di bawahnya. Diukur dari docx asli (Perwakilan User/Pengembang): 3 baris ×
    2 kolom — bar, ruang tanda tangan (ditinggikan ±1 inci), lalu baris nama.

    Beda dari `_heighten_signature_rows` (yang dipakai template `default`, dikenali
    dari header kolom "Tanda Tangan"): di sini judul ADA DI DALAM bar hitam, bukan
    label bold di atas tabel, dan tabelnya 2 kolom tanpa baris header teks.
    """
    for table in document.tables:
        if _take_table_marker(table, _SIGNATURE_BAR_MARKER) is None:
            continue
        _merge_first_row_into_bar(table, _SIGNATURE_BAR_FILL, white_text=True)
        # Baris pertama di bawah bar = ruang tanda tangan basah (±1 inci, seperti
        # kotak tanda tangan acuan); baris berikutnya (nama/jabatan) tetap.
        body = list(table.rows)[1:]
        if body:
            body[0].height = Inches(1.0)
            body[0].height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        _keep_table_together(table)


def _merge_cover_entity_column(document) -> None:
    """Gabung VERTIKAL kolom pertama (Entitas) tabel Tim Project cover bertanda
    _COVER_MERGE_MARKER: satu nilai perusahaan memayungi seluruh baris tim,
    persis tabel "Entitas | Jabatan | Nama" docx PREMCO asli (sel Entitas
    di-merge lintas baris). Nilainya diambil dari sel data pertama; sel di
    bawahnya (sengaja kosong di template) ikut lebur ke atas."""
    for table in document.tables:
        if _take_table_marker(table, _COVER_MERGE_MARKER) is None:
            continue
        body = table.rows[1:]  # lewati baris header
        if len(body) < 2:
            continue
        merged = body[0].cells[0]
        for row in body[1:]:
            merged = merged.merge(row.cells[0])
        merged.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


# Style paragraf blok judul cover (eyebrow, judul, baris identitas) — hanya ini
# yang di-align kanan; tabel kodifikasi/tim di bawahnya tak tersentuh.
_COVER_HEADER_STYLES = ("Cover Eyebrow", "Title", "Cover Subtitle")


def _right_align_cover(document) -> None:
    """Ratakan KANAN blok judul cover (eyebrow "SOLUTION DESIGN DOCUMENT", judul
    project, dan baris identitas No/Versi/RFC/Klasifikasi) — permintaan pemilik
    untuk template premco (meniru posisi identitas cover PREMCO). Dipanggil SESUDAH
    `_split_cover_title` supaya paragraf eyebrow-nya sudah ada. Hanya menyentuh
    paragraf bergaya cover; tabel Fungsi/Katalog/Tim di bawahnya tetap kiri."""
    for paragraph in document.paragraphs:
        if paragraph.style.name in _COVER_HEADER_STYLES:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT


def _is_infra_table(table) -> bool:
    """Tabel Infrastructure & Capacity Planning premco, dikenali dari HEADER-nya
    yang khas: `No. | Resources | <kosong> | Remark` (kolom ke-3 header kosong).
    Tabel lain (Demografi/System Requirement/How to Access/Features) selalu punya
    judul di kolom ke-3, jadi tak mungkin salah kena; template default tak punya
    tabel ini sama sekali (pakai teks bebas)."""
    if not table.rows or len(table.rows[0].cells) != 4:
        return False
    h = [c.text.strip() for c in table.rows[0].cells]
    return h[0] == "No." and h[1] == "Resources" and h[2] == "" and h[3] == "Remark"


def _merge_infra_empty_cells(document) -> None:
    """Di tabel Infrastructure premco, gabung sel kolom sub-environment (idx 2) &
    Remark (idx 3) pada baris yang KEDUANYA kosong — persis docx PREMCO asli, di
    mana baris tanpa sub-environment (Infrastructure Tech Req, Network, Data
    Center) memakai satu sel lebar, bukan dua sel kosong bersebelahan. Baris yang
    sub-environment-nya terisi (Akses URL → Development/QA/…) tidak disentuh."""
    for table in document.tables:
        if not _is_infra_table(table):
            continue
        for row in table.rows[1:]:  # lewati header
            cells = row.cells
            if len(cells) == 4 and not cells[2].text.strip() and not cells[3].text.strip():
                cells[2].merge(cells[3])


def _apply_green_headers(document) -> None:
    """Warnai HIJAU baris header tabel yang sel pertamanya ditandai
    _GREEN_HEADER_MARKER — konvensi tabel test-case UAT PREMCO.

    Beda dari _apply_title_bars: baris header TIDAK di-merge (tetap 9 kolom),
    cuma diberi latar hijau + bold. Header hitam kondisional (firstRow) dimatikan
    untuk tabel ini saja supaya latar hijau tidak tertimpa hitam; perataan tengah
    tetap ditangani _center_table_headers (yang meratakan baris pertama tiap tabel).
    """
    for table in document.tables:
        if _take_table_marker(table, _GREEN_HEADER_MARKER) is None:
            continue
        header = table.rows[0]

        _disable_conditional_header(table)

        for cell in header.cells:
            shading = OxmlElement("w:shd")
            shading.set(qn("w:val"), "clear")
            shading.set(qn("w:color"), "auto")
            shading.set(qn("w:fill"), _GREEN_HEADER_FILL)
            cell._tc.get_or_add_tcPr().append(shading)
            for cell_paragraph in cell.paragraphs:
                for run in cell_paragraph.runs:
                    run.bold = True


def _expand_line_break_markers(document) -> None:
    """Tukar _LINE_BREAK_MARKER di sel tabel dengan line break Word sungguhan.

    Dipakai template premco untuk daftar bernomor DI DALAM sel (acceptance
    criteria, langkah activity — konvensi dokumen aslinya). Lihat komentar di
    konstanta: `<br/>` bukan pilihan, Pandoc membuangnya tanpa suara.
    """
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    if _LINE_BREAK_MARKER not in paragraph.text:
                        continue
                    parts = paragraph.text.split(_LINE_BREAK_MARKER)
                    paragraph.text = parts[0]
                    for part in parts[1:]:
                        run = paragraph.add_run()
                        run.add_break()
                        run.add_text(part)
                    # Rata KIRI: body justified (warisan style) + line break
                    # manual = tiap baris direntangkan Word sampai penuh —
                    # "Admin    membuka    halaman" (terlihat di probe V1).
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT


def _center_table_headers(document) -> None:
    """Ratakan tengah teks baris pertama SETIAP tabel — meniru header tabel
    dokumen acuan.

    Kenapa post-process, bukan style: Word MENGABAIKAN w:pPr (termasuk
    jc=center) yang datang dari conditional formatting `tblStylePr firstRow` di
    table style — diprobe langsung 2026-07-16 lewat export Word sungguhan,
    dengan compat flag overrideTableStyleFontSizeAndJustification true/false/
    absen: ketiganya identik, teks header tetap rata kiri. rPr (bold, warna) dan
    tcPr (latar hitam) dihormati, pPr tidak. Pandoc juga tidak bisa menolong:
    alignment kolom pipe table berlaku SATU KOLOM penuh (header + isi), bukan
    per baris. Jadi satu-satunya tempat deterministik yang tersisa adalah sesudah
    docx-nya jadi.
    """
    for table in document.tables:
        if not table.rows:
            continue
        for cell in table.rows[0].cells:
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER


def _split_cover_title(document) -> None:
    """Pecah judul cover jadi DUA tingkat: label jenis dokumen di atas, nama
    project sebagai judul besar di bawahnya — urutan yang sama dengan cover
    dokumen acuan (label "Solution Design #..." lalu nama project yang lebih
    besar).

    Pandoc menulis SATU paragraf style `Title` berisi "<label> — <project>"
    (lihat `_document_title`), dan teks gabungan itu memang harus tetap utuh:
    dia juga judul di docProps yang dibaca field TITLE di kaki tiap halaman —
    satu sumber, dua tempat. Yang dipecah cuma TAMPILANNYA di halaman cover.

    Kalau tidak ada em dash (project_name kosong), paragraf dibiarkan apa
    adanya — cover jatuh ke rupa lama, bukan error.
    """
    for paragraph in document.paragraphs:
        if paragraph.style.name != "Title":
            continue
        label, separator, project = paragraph.text.partition(" — ")
        if not separator:
            return
        eyebrow = paragraph.insert_paragraph_before(label, style="Cover Eyebrow")
        # Judul besar mewarisi napas atasnya DARI eyebrow yang baru — tanpa ini
        # jarak `before` style Title menumpuk jadi lubang di tengah cover.
        paragraph.paragraph_format.space_before = Pt(0)
        # Tulis ulang isi paragraf judul jadi nama project saja, sambil menjaga
        # run pertamanya (formatnya ikut style Title).
        for extra_run in paragraph.runs[1:]:
            extra_run._r.getparent().remove(extra_run._r)
        if paragraph.runs:
            paragraph.runs[0].text = project
        else:
            paragraph.add_run(project)
        del eyebrow  # cuma disisipkan; tidak ada lagi yang perlu dilakukan padanya
        return


def _strip_marker_in_cell(cell, marker: str) -> None:
    """Buang marker dari sel TANPA menyentuh paragrafnya.

    Sengaja tidak memakai `cell.text = ...`: assignment itu membuang seluruh
    paragraf sel dan menggantinya dengan paragraf baru bergaya Normal — sel
    bermarker jadi lebih tinggi dan berhuruf lebih besar daripada sel lain di
    tabel yang sama (terlihat jelas di probe: baris pertama tiap blok cover
    menonjol sendiri). Yang diganti cukup teks run pertamanya.
    """
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            if run.text.startswith(marker):
                run.text = run.text[len(marker):].lstrip()
                return
    cell.text = cell.text[len(marker):].strip()  # jaring pengaman


def _take_table_marker(table, *markers: str) -> str | None:
    """Marker mana yang menandai tabel ini? Sekaligus MEMBUANGnya dari selnya.

    Template menyatakan maksud ("tabel ini bar judul biru / header hijau / blok
    cover") lewat marker di sel pertama, karena Markdown tak punya cara
    menyatakannya. Deteksi + pembuangannya identik di semua pemakai, jadi
    disatukan di sini — termasuk jaminan bahwa pembuangan marker tidak
    menjatuhkan style paragraf selnya (lihat `_strip_marker_in_cell`).

    Kembalikan marker yang cocok, atau None kalau tabel ini bukan miliknya.
    """
    if not table.rows:
        return None
    first_cell = table.rows[0].cells[0]
    text = first_cell.text
    for marker in markers:
        if text.startswith(marker):
            _strip_marker_in_cell(first_cell, marker)
            return marker
    return None


def _clear_table_borders(table) -> None:
    """Lepas SEMUA garis tabel (termasuk yang datang dari table style)."""
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "none")
        element.set(qn("w:sz"), "0")
        borders.append(element)
    tbl_pr = table._tbl.tblPr
    for old in tbl_pr.findall(qn("w:tblBorders")):
        tbl_pr.remove(old)
    tbl_pr.append(borders)


def _set_row_bottom_rule(row, color: str) -> None:
    """Hairline di bawah satu baris — dipasang per SEL, karena tblBorders sudah
    dimatikan seluruhnya (garis per-sel yang menang, bukan sebaliknya)."""
    for cell in row.cells:
        tc_pr = cell._tc.get_or_add_tcPr()
        for old in tc_pr.findall(qn("w:tcBorders")):
            tc_pr.remove(old)
        borders = OxmlElement("w:tcBorders")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "4")
        bottom.set(qn("w:color"), color)
        borders.append(bottom)
        tc_pr.append(borders)


def _flush_cover_cell_margins(table) -> None:
    """Nolkan padding KIRI/KANAN sel blok cover; sisakan padding atas/bawah.

    Tanpa ini isi blok masuk ~0,08 inci ke dalam relatif label section dan garis
    pemisah di atasnya — tepi kiri cover jadi bergerigi, dan itu persis yang
    paling terlihat pada desain yang bersandar pada perataan. Padding vertikal
    tetap ada: yang memberi baris ruang bernapas.
    """
    tbl_pr = table._tbl.tblPr
    for old in tbl_pr.findall(qn("w:tblCellMar")):
        tbl_pr.remove(old)
    margins = OxmlElement("w:tblCellMar")
    for edge, width in (("top", 70), ("left", 0), ("bottom", 70), ("right", 0)):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:w"), str(width))
        element.set(qn("w:type"), "dxa")
        margins.append(element)
    tbl_pr.append(margins)


def _disable_conditional_header(table) -> None:
    """Matikan format kondisional baris pertama (header hitam) untuk satu tabel."""
    tbl_look = table._tbl.tblPr.find(qn("w:tblLook"))
    if tbl_look is not None:
        tbl_look.set(qn("w:firstRow"), "0")


def _style_cover_blocks(document) -> None:
    """Ubah tabel bermarker cover jadi blok TANPA rupa tabel.

    Kenapa post-process, bukan style: Pandoc tidak menyediakan cara menunjuk
    table style per-tabel (semua tabel memakai style "Table" yang sama), dan
    Markdown tidak punya sintaks "tabel tanpa garis". Pola yang sama persis
    dengan ((BAR)) dan ((GH)) — template menyatakan MAKSUD lewat marker, rupa
    dikerjakan di sini.

    Dijalankan SESUDAH `_center_table_headers` (yang meratakan tengah baris
    pertama SETIAP tabel): blok daftar cover tidak punya baris header sama
    sekali, jadi perataannya harus dikembalikan ke kiri di sini.
    """
    for table in document.tables:
        marker = _take_table_marker(table, _COVER_BAND_MARKER, _COVER_LIST_MARKER)
        if marker is None:
            continue
        band = marker == _COVER_BAND_MARKER

        _disable_conditional_header(table)
        _clear_table_borders(table)
        _flush_cover_cell_margins(table)

        if band:
            # Pita identitas: baris 1 = label kecil huruf besar abu, baris 2 =
            # nilainya besar & tebal. Dua baris, satu makna — jadi label sengaja
            # jauh lebih kecil dari nilainya (kontras yang membuat pita ini
            # terbaca sebagai hierarki, bukan sebagai tabel tanpa garis).
            for index, row in enumerate(table.rows):
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        for run in paragraph.runs:
                            run.bold = index > 0
                            run.font.size = Pt(13 if index else 8.5)
                            if index == 0:
                                run.font.all_caps = True
                                run.font.color.rgb = RGBColor.from_string(_COVER_LABEL_INK)
            continue

        # Daftar label→nilai: hairline antar-baris (baris terakhir TANPA garis,
        # supaya blok berakhir dengan tenang, bukan dengan garis menggantung),
        # kolom label abu supaya nilainya yang menonjol.
        for row in table.rows[:-1]:
            _set_row_bottom_rule(row, _COVER_RULE_INK)
        for row in table.rows:
            for index, cell in enumerate(row.cells):
                for paragraph in cell.paragraphs:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    for run in paragraph.runs:
                        if index == 0:
                            run.font.color.rgb = RGBColor.from_string(_COVER_LABEL_INK)


def _set_keep_next(paragraph_element) -> None:
    """Pasang w:keepNext pada satu elemen w:p (urutan schema pPr: pStyle dulu)."""
    p_pr = paragraph_element.find(qn("w:pPr"))
    if p_pr is None:
        p_pr = OxmlElement("w:pPr")
        paragraph_element.insert(0, p_pr)
    if p_pr.find(qn("w:keepNext")) is None:
        keep_next = OxmlElement("w:keepNext")
        p_style = p_pr.find(qn("w:pStyle"))
        if p_style is not None:
            p_style.addnext(keep_next)
        else:
            p_pr.insert(0, keep_next)


_FIGURE_STYLES = ("Figure", "Captioned Figure")


def _bind_lead_in_to_figure(document) -> None:
    """Ikat paragraf PENGANTAR ke gambar yang mengikutinya (keepNext).

    Style `Figure` sudah keepNext ke CAPTION-nya, jadi gambar+caption selalu
    sekelompok. Yang belum: kalau gambar itu tidak muat di sisa halaman, dia
    pindah SENDIRI dan meninggalkan judul sub-bab + kalimat pengantarnya
    terdampar di kaki halaman sebelumnya dengan ruang kosong menganga di
    bawahnya (terlihat di probe: "ACTIVITY DIAGRAM" + satu kalimat, lalu 2,5
    inci kosong). Heading sendiri sudah keepNext ke pengantarnya; dengan
    mengikat pengantar → gambar, seluruh kelompok heading→pengantar→gambar→
    caption berpindah utuh.

    Dikerjakan di sini, bukan di style: "paragraf ini kebetulan mendahului
    gambar" adalah fakta tentang URUTAN dokumen, bukan tentang jenis
    paragrafnya — style tidak punya cara menyatakannya.
    """
    paragraphs = document.paragraphs
    for current, following in zip(paragraphs, paragraphs[1:]):
        if following.style.name not in _FIGURE_STYLES:
            continue
        if current.style.name in _FIGURE_STYLES or not current.text.strip():
            continue
        _set_keep_next(current._p)


def _move_table_captions_below(document) -> None:
    """Pindahkan caption tabel ("Tabel N ...") ke BAWAH tabelnya — posisi yang
    dipakai dokumen acuan. Pandoc selalu menulis caption SEBELUM tabel dan tidak
    menyediakan tombol untuk memindahnya, jadi posisinya direbut sesudah docx
    jadi — mekanisme yang sama dengan _center_table_headers.

    Dua hal yang menjaga caption tidak terpisah dari tabelnya di batas halaman:
    (1) style "Table Caption" TIDAK lagi membawa keepNext (dulu perlu, saat
    caption di atas — sekarang malah mengikat caption ke paragraf SESUDAHNYA,
    arah yang salah); (2) seluruh paragraf di BARIS TERAKHIR tabel diberi
    keepNext di sini — trik standar Word untuk mengikat tabel ke paragraf yang
    mengikutinya.
    """
    body = document.element.body
    for table in body.findall(qn("w:tbl")):
        caption = table.getprevious()
        if caption is None or caption.tag != qn("w:p"):
            continue
        ppr = caption.find(qn("w:pPr"))
        style = ppr.find(qn("w:pStyle")) if ppr is not None else None
        if style is None or style.get(qn("w:val")) != "TableCaption":
            continue
        table.addnext(caption)
        rows = table.findall(qn("w:tr"))
        if not rows:
            continue
        for paragraph in rows[-1].iter(qn("w:p")):
            _set_keep_next(paragraph)


def _heighten_signature_rows(document) -> None:
    """Baris kosong tabel tanda tangan ditinggikan jadi ruang tanda tangan
    basah (min. 1 inci) — di dokumen acuan kotak tanda tangannya setinggi
    ±4 cm, sementara baris tabel biasa cuma setinggi satu baris teks.

    Tabelnya dikenali dari isinya (ada sel header "Tanda Tangan"), bukan dari
    posisinya: template boleh berpindah-pindah susunan tanpa merusak ini, dan
    tabel lain tidak mungkin kena karena tidak ada yang memakai judul kolom itu.
    Style tabel tidak bisa menolong di sini — tinggi baris dari style berlaku
    ke SEMUA tabel, padahal yang butuh tinggi cuma baris tanda tangan.

    Bloknya juga diikat supaya UTUH pindah halaman: begitu barisnya setinggi
    1 inci, tabelnya gampang patah tepat sesudah header — label "Perwakilan X"
    + header yatim di dasar halaman, isinya di halaman berikut (kejadian di
    probe). keepNext dipasang di label pengantar + semua baris kecuali terakhir,
    persis blok tanda tangan acuan yang selalu utuh satu halaman.
    """
    for table in document.tables:
        if not table.rows:
            continue
        header_texts = {cell.text.strip() for cell in table.rows[0].cells}
        if "Tanda Tangan" not in header_texts:
            continue
        rows = list(table.rows)
        for row in rows[1:]:
            row.height = Inches(1)
            row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        for row in rows[:-1]:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    _set_keep_next(paragraph._p)
        label = table._tbl.getprevious()
        if label is not None and label.tag == qn("w:p"):
            _set_keep_next(label)


def _trim_transparent_edges(logo_bytes: bytes) -> tuple[bytes, tuple[int, int]]:
    """Pangkas tepi TRANSPARAN logo; kembalikan (bytes, ukuran) hasilnya.

    File logo dunia nyata sering berupa gambar kecil di tengah kanvas besar —
    kasus nyata yang memicu ini: logo 964x288 di kanvas 1024x576, padding
    transparan 144 px atas-bawah. Ditanam apa adanya "setinggi 0,45 inci",
    yang KELIHATAN cuma 0,22 inci — kerdil, dan meleset dari posisi.

    Hanya alpha yang dipangkas: memangkas "tepi putih" JPEG itu tebak-tebakan
    (putih bisa bagian logonya), sementara piksel ber-alpha-nol memang
    dinyatakan kosong oleh file-nya sendiri.
    """
    with Image.open(io.BytesIO(logo_bytes)) as image:
        if "A" in image.getbands():
            content_box = image.getchannel("A").getbbox()
            if content_box and content_box != (0, 0, image.width, image.height):
                cropped = image.crop(content_box)
                buffer = io.BytesIO()
                cropped.save(buffer, format="PNG")
                return buffer.getvalue(), cropped.size
        return logo_bytes, image.size


def _add_header_logo(document, logo_bytes: bytes) -> None:
    """Tanam logo di kanan atas header SETIAP halaman — posisi logo dokumen
    acuan enterprise.

    Kenapa di post-process, bukan di reference.docx: reference.docx itu statis
    dan dibangun sekali oleh script, sementara logo datang PER REQUEST dari
    form. Satu-satunya tempat mempertemukan keduanya adalah sesudah docx jadi.

    Ukuran tampil dihitung dari piksel KONTENNYA (sesudah tepi transparan
    dipangkas): tinggi standar 0,45 inci, tapi logo pita yang sangat lebar
    dibatasi LEBARNYA — logo 10:1 yang dipaksa setinggi 0,45 inci berarti
    selebar 4,5 inci, menabrak area teks.
    """
    logo_bytes, (width_px, height_px) = _trim_transparent_edges(logo_bytes)
    if width_px / height_px > _LOGO_MAX_WIDTH_IN / _LOGO_HEIGHT_IN:
        size = {"width": Inches(_LOGO_MAX_WIDTH_IN)}
    else:
        size = {"height": Inches(_LOGO_HEIGHT_IN)}

    for section in document.sections:
        header = section.header
        # Dokumen dari Pandoc tidak punya header part sama sekali — akses lewat
        # is_linked_to_previous membuat part kosongnya dulu.
        header.is_linked_to_previous = False
        paragraph = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        paragraph.add_run().add_picture(io.BytesIO(logo_bytes), **size)


def _set_section_orientation(section, orient: str) -> None:
    """Set orientasi satu section lewat API python-docx, BUKAN tukar atribut
    mentah: reference.docx tak punya `<w:pgSz>` sama sekali (page size-nya
    default), jadi tidak ada yang bisa ditukar — setter page_width/height yang
    membuatnya. Letter landscape (11x8,5) / potret (8,5x11), margin 1 inci."""
    if orient == "landscape":
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width = Inches(11)
        section.page_height = Inches(8.5)
    else:
        section.orientation = WD_ORIENT.PORTRAIT
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)


def _apply_orientation_markers(document) -> None:
    """Pecah dokumen di tiap marker orientasi: `((LANDSCAPE))` memutar bagian
    SESUDAHnya jadi landscape, `((PORTRAIT))` mengembalikannya jadi potret.

    Mekanisme OOXML: properti sebuah section disimpan di sectPr yang
    MENGAKHIRInya. Jadi tiap paragraf marker diberi sectPr berisi orientasi
    segmen yang BERJALAN SAMPAI SITU, lalu orientasi berjalan berganti; sectPr
    body (yang selalu jadi section TERAKHIR) memayungi segmen penghabisan.

    Dulu fungsi ini cuma menangani SATU marker (`_landscape_after_marker`):
    potret → landscape sampai akhir dokumen, cukup untuk UAT premco yang
    memang begitu bentuknya. Digeneralisasi saat template hasil-upload mulai
    membawa orientasinya sendiri — template sembarang bisa punya satu bab
    landscape di TENGAH lalu kembali potret, dan mekanisme satu-marker
    memaksa sisa dokumen ikut landscape. Satu marker `((LANDSCAPE))` sendirian
    tetap menghasilkan perilaku yang sama persis seperti dulu.

    Dijalankan sebelum _add_header_logo agar logo (yang meloop
    document.sections) menjangkau SEMUA section."""
    body = document.element.body
    markers = []
    for paragraph in body.findall(qn("w:p")):
        text = "".join(t.text or "" for t in paragraph.iter(qn("w:t"))).strip()
        if text in (_LANDSCAPE_MARKER, _PORTRAIT_MARKER):
            markers.append((paragraph, "landscape" if text == _LANDSCAPE_MARKER
                            else "portrait"))
    if not markers:
        return

    section_props = body.findall(qn("w:sectPr"))
    if not section_props:
        return
    body_sectpr = section_props[-1]

    for marker_p, _ in markers:
        # sectPr (salinan) → menutup segmen berjalan tepat di paragraf marker.
        closing = copy.deepcopy(body_sectpr)
        p_pr = marker_p.find(qn("w:pPr"))
        if p_pr is None:
            p_pr = OxmlElement("w:pPr")
            marker_p.insert(0, p_pr)
        p_pr.append(closing)
        # Kosongkan teks marker — paragrafnya jadi penutup section (tak terlihat).
        for run in list(marker_p.findall(qn("w:r"))):
            marker_p.remove(run)

    # Sesudah N marker ditanam, dokumen punya N+1 section. Section pertama
    # adalah yang SEBELUM marker pertama (selalu potret — dokumen mulai potret);
    # section ke-i sesudahnya memakai orientasi yang dideklarasikan marker ke-i.
    orientations = ["portrait"] + [orient for _, orient in markers]
    for section, orient in zip(document.sections, orientations):
        _set_section_orientation(section, orient)


def _postprocess_docx(docx_path: str, logo_bytes: bytes | None = None,
                      cover_align_right: bool = False) -> None:
    """Sentuhan yang tidak bisa dititipkan ke reference.docx maupun Pandoc —
    satu kali buka-simpan untuk semuanya."""
    document = docx.Document(docx_path)
    _apply_title_bars(document)  # sebelum center: baris pertama masih utuh per-sel
    _apply_signature_bars(document)  # bar hitam blok tanda tangan premco (idem)
    _merge_cover_entity_column(document)  # kolom Entitas cover premco -> merge vertikal
    _merge_infra_empty_cells(document)  # tabel Infrastructure premco -> gabung sel kosong
    _apply_green_headers(document)  # header hijau tabel test-case UAT premco
    _expand_line_break_markers(document)
    _center_table_headers(document)
    _split_cover_title(document)  # judul cover -> label + nama project
    if cover_align_right:
        _right_align_cover(document)  # SESUDAH split: eyebrow sudah ada untuk di-align
    _style_cover_blocks(document)  # SESUDAH center: daftar cover kembali rata kiri
    _bind_lead_in_to_figure(document)
    _move_table_captions_below(document)
    _heighten_signature_rows(document)
    _apply_orientation_markers(document)  # ((LANDSCAPE))/((PORTRAIT)) → section
    if logo_bytes:
        _add_header_logo(document, logo_bytes)
    document.save(docx_path)


def _steps_to_br(text: str) -> str:
    """Ubah teks multi-baris jadi satu string ber-marker ((BR)) — dipakai template
    premco untuk menaruh langkah pengujian bernomor DI DALAM sel tabel. Baris
    kosong dibuang; satu baris tetap satu baris (tanpa marker)."""
    lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
    return _LINE_BREAK_MARKER.join(lines)


def _group_test_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Kelompokkan test case per `module`, mempertahankan urutan kemunculan.
    Kalau tidak ada test case yang punya `module` (mis. Contract B belum
    memuat field itu), hasilnya SATU grup tanpa nama — template merender satu
    tabel hijau tanpa sub-judul modul (fallback aman)."""
    groups: list[dict[str, Any]] = []
    by_key: dict[str | None, dict[str, Any]] = {}
    for tc in cases:
        key = (str(tc.get("module") or "")).strip() or None
        if key not in by_key:
            by_key[key] = {"group_name": key, "test_cases": []}
            groups.append(by_key[key])
        by_key[key]["test_cases"].append(tc)
    return groups


def _build_uat_context(data: dict[str, Any], group: bool = False) -> dict[str, Any]:
    cases = data.get("uat_test_cases", [])
    if group:
        # Langkah & hasil jadi multi-baris di dalam sel (marker ((BR))), lalu
        # dikelompokkan per modul → tabel test-case per-layar ala UAT PREMCO
        # (premco) atau template hasil-generate (yang juga pakai tabel per-modul).
        prepared = [
            {
                **tc,
                "steps": _steps_to_br(tc.get("steps", "")),
                "expected_result": _steps_to_br(tc.get("expected_result", "")),
            }
            for tc in cases
        ]
        return {**data, "uat_test_groups": _group_test_cases(prepared)}
    # default: satu baris tabel Markdown wajib satu baris teks → newline jadi "; ".
    cleaned_cases = [
        {**tc, "steps": tc["steps"].replace("\n", "; ")}
        for tc in cases
    ]
    return {**data, "uat_test_cases": cleaned_cases}


def generate_docx(
    document_type: str,
    document_content: dict[str, Any],
    project_name: str = "",
    document_metadata: dict[str, Any] | None = None,
    logo_bytes: bytes | None = None,
    template_id: str = "default",
) -> str:
    """
    Entry point utama Peran 3.

    document_type: "SDD" atau "UAT" (menentukan template mana yang dipakai).
    document_content: dict hasil DocumentContent.model_dump() dari LLMService
                       milik Peran 2 (Contract B), atau dummy JSON dengan
                       skema yang sama.
    document_metadata: isian manusia dari form (nomor RFC, demografi, dst).
                       None/kosong = template pakai penanda *(diisi manual)*
                       seperti sebelum form ini ada.
    logo_bytes: bytes gambar logo yang SUDAH tervalidasi (lihat decode_logo) —
                ditanam di header tiap halaman. None = tanpa header logo,
                persis perilaku sebelum fitur ini ada.
    template_id: gaya dokumen dari _TEMPLATE_REGISTRY ("default"/"premco") —
                 lihat komentar registry. Kombinasi yang tidak tersedia =
                 ValueError.
    Mengembalikan path file .docx yang sudah jadi.
    """
    normalized_type = document_type.upper()
    if normalized_type not in ("SDD", "UAT"):
        raise ValueError(f"document_type tidak dikenal: {document_type!r} (harus 'SDD' atau 'UAT')")
    validate_template(template_id, normalized_type)
    resolved = _resolve_template(template_id, normalized_type)

    context = {
        "project_name": project_name,
        "meta": _build_metadata_context(document_metadata),
        **document_content,
    }

    if normalized_type == "SDD":
        context = {**context,
                   **_build_sdd_context(document_content, resolved.uses_component_integration)}
    else:
        context = {**context,
                   **_build_uat_context(document_content, resolved.groups_test_cases)}

    rendered_markdown = resolved.template.render(**context)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{normalized_type}_{uuid.uuid4().hex}.docx"

    try:
        pypandoc.convert_text(
            rendered_markdown,
            to="docx",
            format="md",
            outputfile=str(output_path),
            extra_args=_pandoc_args(
                normalized_type,
                _document_title(normalized_type, project_name),
                resolved.reference_docx,
                resolved.uat_toc,
            ),
        )
    except OSError as e:
        raise RuntimeError(
            "Pandoc tidak ditemukan di sistem. Install pandoc terlebih dahulu "
            "(https://pandoc.org/installing.html) atau jalankan "
            "`python -c \"import pypandoc; pypandoc.download_pandoc()\"` sekali."
        ) from e

    _postprocess_docx(
        str(output_path),
        logo_bytes,
        cover_align_right=resolved.cover_align_right and normalized_type == "SDD",
    )
    return str(output_path)
