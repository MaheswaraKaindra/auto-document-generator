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
from docx.enum.table import WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches
from jinja2 import Environment, FileSystemLoader
from PIL import Image, UnidentifiedImageError

from app.core import config
from app.diagram.ir import Actor, Association, UseCaseDiagramIR, UseCaseNode
from app.diagram.renderer import PlantUMLRenderer
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
_BUILTIN_SPLITS_USECASE = {"default", "premco"}   # SDD: pecah diagram use case per-aktor (panah lebih jelas)


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
    splits_usecase: bool = False      # SDD: pecah diagram use case jadi satu per-aktor?


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
            splits_usecase=template_id in _BUILTIN_SPLITS_USECASE,
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
# bukan dari output model yang bisa berubah-ubah antar panggilan. `!theme plain`
# = UML klasik hitam-putih, gaya yang dipakai dokumen acuan enterprise.
_PLANTUML_STYLE_PREAMBLE = ("!theme plain", f"skinparam dpi {_PLANTUML_DPI}")

# Ruang yang benar-benar tersedia di halaman, dipakai _image_attr untuk membatasi
# ukuran tampil diagram. Lebar: 8,5 inci dikurangi margin 1 inci di dua sisi.
# Tinggi: 11 dikurangi margin, dikurangi lagi ruang untuk judul sub-bab dan
# caption di bawah gambar — 8 inci konservatif, dan lebih baik diagram sedikit
# lebih kecil daripada tumpah ke halaman berikutnya.
_PAGE_WIDTH_IN = 6.5
_PAGE_HEIGHT_IN = 8.0

# Berapa piksel PNG per inci TAMPIL di dokumen. Ini kunci dua cacat visual
# sekaligus: (1) diagram kecil yang DIRENTANGKAN selebar halaman jadi buram +
# hurufnya raksasa — jangan pernah upscale; (2) teks diagram harus seragam antar
# diagram. 360 px/inci pada render 300 dpi ≈ teks ~9pt di kertas (sedikit di
# bawah body 11pt, seperti diagram dokumen acuan) dengan ketajaman efektif
# 360 dpi. Menaikkan angka ini = teks lebih kecil & lebih tajam.
_DIAGRAM_DISPLAY_DPI = 360

_MANUAL_PLACEHOLDER = "*(diisi manual)*"

# Bar judul tabel gaya PREMCO (baris pertama tabel di-merge jadi satu sel biru
# muda berjudul). Pipe table Markdown tidak bisa merge sel, jadi template
# menandai baris pertamanya dengan marker ini dan post-process yang mengubahnya
# jadi bar sungguhan. Warna birunya TERUKUR dari docx PREMCO asli (27 sel),
# bukan ditebak.
_TITLE_BAR_MARKER = "((BAR))"
_TITLE_BAR_FILL = "9CC3E5"

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


def _normalize_plantuml(diagram_script: str) -> str:
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
            lines.extend(_PLANTUML_STYLE_PREAMBLE)
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


def _render_diagram_to_image(diagram_script: str, images_dir: Path) -> str:
    """Render satu script PlantUML jadi file PNG lokal; kembalikan path-nya."""
    images_dir.mkdir(parents=True, exist_ok=True)
    png = _run_plantuml(_normalize_plantuml(diagram_script))
    image_path = images_dir / f"{uuid.uuid4().hex}.png"
    image_path.write_bytes(png)
    return str(image_path)


# --- Split use case diagram per-aktor -----------------------------------------
# Diagram use case dengan banyak aktor yang berbagi banyak use case membuat
# panah menyilang-menumpuk (keterbatasan auto-layout smetana) — sulit dibaca
# (temuan dari dokumen user Flowy, 2026-07-20). Solusinya: pecah jadi satu
# diagram BERSIH per aktor. Datanya diambil dengan mem-PARSE PlantUML use case
# karangan LLM (grammar-nya dibatasi SYSTEM_PROMPT: actor/rectangle/usecase/-->),
# lalu dirender ulang lewat layer Diagram IR (PlantUMLRenderer). Tak menyentuh
# LLM/prompt/DocumentContent; kalau parse/render gagal → None → pemanggil
# fallback ke diagram tunggal (nol regresi).
_UC_ACTOR_ALIAS = re.compile(r'^\s*actor\s+"([^"]+)"\s+as\s+(\w+)', re.M)
_UC_ACTOR_BARE = re.compile(r"^\s*actor\s+(\w+)\s*$", re.M)
_UC_USECASE = re.compile(r'usecase\s+"([^"]+)"\s+as\s+(\w+)')
_UC_RECTANGLE = re.compile(r'rectangle\s+"([^"]+)"')
_UC_ASSOC = re.compile(r"^\s*(\w+)\s*-->\s*(\w+)", re.M)


def _usecase_plantuml_to_ir(script: str) -> UseCaseDiagramIR | None:
    """Parse PlantUML use case (subset grammar LLM) → UseCaseDiagramIR, atau None
    kalau tak cocok (→ fallback). Toleran: apa pun yang tak dikenali diabaikan."""
    actors: dict[str, str] = {}
    for label, alias in _UC_ACTOR_ALIAS.findall(script):
        actors[alias] = label
    for name in _UC_ACTOR_BARE.findall(script):
        actors.setdefault(name, name)          # `actor Admin` → id=label=Admin
    use_cases = {ucid: label for label, ucid in _UC_USECASE.findall(script)}
    if not actors or not use_cases:
        return None

    rect = _UC_RECTANGLE.search(script)
    associations = []
    for a, b in _UC_ASSOC.findall(script):
        # arah asosiasi bisa Actor-->UC atau UC-->Actor; normalkan ke (aktor, uc)
        if a in actors and b in use_cases:
            associations.append((a, b))
        elif b in actors and a in use_cases:
            associations.append((b, a))
    if not associations:
        return None
    return UseCaseDiagramIR(
        system_name=rect.group(1) if rect else "System",
        actors=[Actor(id=i, label=l) for i, l in actors.items()],
        use_cases=[UseCaseNode(id=i, label=l) for i, l in use_cases.items()],
        associations=[Association(actor=a, use_case=u) for a, u in associations],
    )


def _split_usecase_images(script: str, images_dir: Path) -> list[dict] | None:
    """PlantUML use case → daftar `{actor, image, attr}` per aktor (satu diagram
    bersih per aktor). None kalau tak bisa/tak berguna di-split (< 2 aktor, parse
    gagal, atau render gagal) — pemanggil fallback ke diagram tunggal."""
    ir = _usecase_plantuml_to_ir(script)
    if ir is None or len(ir.actors) < 2:
        return None
    renderer = PlantUMLRenderer()
    out = []
    for actor in ir.actors:
        uc_ids = {a.use_case for a in ir.associations if a.actor == actor.id}
        if not uc_ids:
            continue
        sub = UseCaseDiagramIR(
            system_name=ir.system_name,
            actors=[actor],
            use_cases=[u for u in ir.use_cases if u.id in uc_ids],
            associations=[a for a in ir.associations if a.actor == actor.id],
        )
        try:
            path = _render_diagram_to_image(renderer.render(sub), images_dir)
        except DiagramRenderError:
            return None                        # render gagal → fallback tunggal
        out.append({"actor": actor.label, "image": path, "attr": _image_attr(path)})
    return out if len(out) >= 2 else None


def _image_attr(image_path: str) -> str:
    """Atribut ukuran Pandoc (`{width=...}` / `{height=...}`) untuk satu diagram.

    Dua aturan, dua cacat yang dicegah:

    1. JANGAN UPSCALE. Ukuran tampil alami = piksel / _DIAGRAM_DISPLAY_DPI.
       Aturan lama merentangkan SEMUA diagram selebar halaman — diagram kecil
       (mis. component diagram 3 kotak) jadi buram dengan huruf raksasa, dan
       ukuran teks antar diagram tidak konsisten. Kalau muat, pakai ukuran alami.
    2. Kalau tidak muat, ciutkan di sisi yang lebih dulu mentok: diagram lebar
       dibatasi LEBARNYA, diagram tinggi dibatasi TINGGINYA — sisi satunya ikut
       proporsional, jadi tidak ada yang gepeng. (Kasus lama yang terukur pada
       esteler: 5 dari 11 diagram setinggi 9,7-17,2 inci di halaman 11 inci.)

    Pillow, bukan parsing header PNG manual: JPEG yang dibaca sebagai PNG
    menghasilkan angka ngawur TANPA error (65536 x 4293001688 — betulan terjadi
    di sesi ini). Pillow memvalidasi formatnya dan gagal berisik.
    """
    with Image.open(image_path) as image:
        width, height = image.size
    natural_width_in = width / _DIAGRAM_DISPLAY_DPI
    natural_height_in = height / _DIAGRAM_DISPLAY_DPI
    if natural_width_in <= _PAGE_WIDTH_IN and natural_height_in <= _PAGE_HEIGHT_IN:
        return f"{{width={natural_width_in:.2f}in}}"
    if height / width > _PAGE_HEIGHT_IN / _PAGE_WIDTH_IN:
        return f"{{height={_PAGE_HEIGHT_IN}in}}"
    return f"{{width={_PAGE_WIDTH_IN}in}}"


def _build_sdd_context(data: dict[str, Any], render_integration: bool = True,
                       split_usecase: bool = False) -> dict[str, Any]:
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
    business_flow = _render_diagram_to_image(diagrams["business_process_flow"], IMAGES_DIR)
    # Use case: template yang mendukung boleh memecah jadi satu diagram per aktor
    # (panah lebih jelas — temuan Flowy 2026-07-20). Kalau tak bisa/tak berguna
    # (< 2 aktor, parse/render gagal) → None → satu diagram gabungan (nol regresi).
    use_case_per_actor = (
        _split_usecase_images(diagrams["use_case_diagram"], IMAGES_DIR)
        if split_usecase else None
    )
    use_case = (None if use_case_per_actor
                else _render_diagram_to_image(diagrams["use_case_diagram"], IMAGES_DIR))

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
            "use_case_diagram_attr": _image_attr(use_case) if use_case else "",
            # None (pakai diagram tunggal di atas) ATAU list[{actor,image,attr}] per aktor.
            "use_case_diagrams_by_actor": use_case_per_actor,
            # Jumlah GAMBAR use case (untuk offset penomoran gambar activity di template).
            "use_case_figure_count": len(use_case_per_actor) if use_case_per_actor else 1,
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
                    (a, _render_diagram_to_image(a["diagram_script"], IMAGES_DIR))
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
        if not table.rows:
            continue
        first_row = table.rows[0]
        if not first_row.cells[0].text.startswith(_TITLE_BAR_MARKER):
            continue
        title = first_row.cells[0].text[len(_TITLE_BAR_MARKER):].strip()

        # Matikan header hitam kondisional (firstRow) untuk tabel INI saja.
        tbl_look = table._tbl.tblPr.find(qn("w:tblLook"))
        if tbl_look is not None:
            tbl_look.set(qn("w:firstRow"), "0")

        merged = first_row.cells[0]
        for cell in first_row.cells[1:]:
            merged = merged.merge(cell)
        merged.text = title
        paragraph = merged.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in paragraph.runs:
            run.bold = True
        shading = OxmlElement("w:shd")
        shading.set(qn("w:val"), "clear")
        shading.set(qn("w:color"), "auto")
        shading.set(qn("w:fill"), _TITLE_BAR_FILL)
        merged._tc.get_or_add_tcPr().append(shading)

        # Ikat tabelnya supaya UTUH pindah halaman — tanpa ini tabel kecil
        # ber-bar gampang patah tepat sesudah bar-nya, dan bar (yang juga
        # tblHeader) terulang membingungkan (terlihat di probe V1, kembaran
        # persis kasus blok tanda tangan).
        rows = list(table.rows)
        for row in rows[:-1]:
            for cell in row.cells:
                for cell_paragraph in cell.paragraphs:
                    _set_keep_next(cell_paragraph._p)


def _apply_green_headers(document) -> None:
    """Warnai HIJAU baris header tabel yang sel pertamanya ditandai
    _GREEN_HEADER_MARKER — konvensi tabel test-case UAT PREMCO.

    Beda dari _apply_title_bars: baris header TIDAK di-merge (tetap 9 kolom),
    cuma diberi latar hijau + bold. Header hitam kondisional (firstRow) dimatikan
    untuk tabel ini saja supaya latar hijau tidak tertimpa hitam; perataan tengah
    tetap ditangani _center_table_headers (yang meratakan baris pertama tiap tabel).
    """
    for table in document.tables:
        if not table.rows:
            continue
        header = table.rows[0]
        if not header.cells[0].text.startswith(_GREEN_HEADER_MARKER):
            continue
        header.cells[0].text = header.cells[0].text[len(_GREEN_HEADER_MARKER):].strip()

        # Matikan header hitam kondisional (firstRow) untuk tabel INI saja.
        tbl_look = table._tbl.tblPr.find(qn("w:tblLook"))
        if tbl_look is not None:
            tbl_look.set(qn("w:firstRow"), "0")

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


def _landscape_after_marker(document) -> None:
    """Pecah dokumen di paragraf _LANDSCAPE_MARKER: bagian SEBELUMnya tetap
    potret, bagian SESUDAHnya (Case Pengujian UAT premco) jadi LANDSCAPE.

    Mekanisme OOXML: properti sebuah section disimpan di sectPr yang MENGAKHIRI-
    nya. Jadi: (1) salin sectPr body (potret) ke pPr paragraf marker → itu
    menutup section potret di sana; (2) putar sectPr body sendiri jadi landscape
    → itu jadi section terakhir, memayungi Case Pengujian sampai akhir dokumen.
    Marker-driven supaya template lain tak tersentuh; hanya premco UAT yang
    memancarkannya. Dijalankan sebelum _add_header_logo agar logo (yang meloop
    document.sections) menjangkau KEDUA section."""
    body = document.element.body
    marker_p = None
    for paragraph in body.findall(qn("w:p")):
        text = "".join(t.text or "" for t in paragraph.iter(qn("w:t")))
        if text.strip() == _LANDSCAPE_MARKER:
            marker_p = paragraph
            break
    if marker_p is None:
        return

    section_props = body.findall(qn("w:sectPr"))
    if not section_props:
        return
    body_sectpr = section_props[-1]

    # (1) sectPr potret (salinan) → menutup section potret di paragraf marker.
    #     Salinan ini SENGAJA tanpa pgSz (reference.docx tak punya) → mewarisi
    #     Letter potret default, persis halaman depan sekarang.
    portrait = copy.deepcopy(body_sectpr)
    p_pr = marker_p.find(qn("w:pPr"))
    if p_pr is None:
        p_pr = OxmlElement("w:pPr")
        marker_p.insert(0, p_pr)
    p_pr.append(portrait)

    # Kosongkan teks marker — paragrafnya jadi penutup section (tak terlihat).
    for run in list(marker_p.findall(qn("w:r"))):
        marker_p.remove(run)

    # (2) Section terakhir (sectPr body) → landscape. Lewat API python-docx,
    #     BUKAN tukar atribut mentah: reference.docx tak punya <w:pgSz> sama
    #     sekali (page size-nya default), jadi tidak ada yang bisa ditukar —
    #     setter page_width/height membuat pgSz-nya. Letter landscape (11x8,5),
    #     margin 1 inci → area teks 9 inci untuk 9 kolom.
    landscape_section = document.sections[-1]
    landscape_section.orientation = WD_ORIENT.LANDSCAPE
    landscape_section.page_width = Inches(11)
    landscape_section.page_height = Inches(8.5)
    landscape_section.left_margin = Inches(1)
    landscape_section.right_margin = Inches(1)


def _postprocess_docx(docx_path: str, logo_bytes: bytes | None = None) -> None:
    """Sentuhan yang tidak bisa dititipkan ke reference.docx maupun Pandoc —
    satu kali buka-simpan untuk semuanya."""
    document = docx.Document(docx_path)
    _apply_title_bars(document)  # sebelum center: baris pertama masih utuh per-sel
    _apply_green_headers(document)  # header hijau tabel test-case UAT premco
    _expand_line_break_markers(document)
    _center_table_headers(document)
    _move_table_captions_below(document)
    _heighten_signature_rows(document)
    _landscape_after_marker(document)  # Case Pengujian UAT premco → landscape
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
                   **_build_sdd_context(document_content, resolved.uses_component_integration,
                                        resolved.splits_usecase)}
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

    _postprocess_docx(str(output_path), logo_bytes)
    return str(output_path)
