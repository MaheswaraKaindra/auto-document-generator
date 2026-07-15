"""
Compiler service (Peran 3 — Backend & Templating).

Alur: DocumentContent (Contract B, dari LLMService milik Peran 2)
      -> render diagram Mermaid jadi gambar
      -> render template Jinja2 (Markdown)
      -> export ke .docx lewat pypandoc.

Tidak menyentuh/menduplikasi logika Peran 1 (parser_service.py) atau
Peran 2 (llm_service.py) — modul ini murni konsumen dari Contract B.
"""

import base64
import json
import tempfile
import uuid
import zlib
from pathlib import Path
from typing import Any

import pypandoc
import requests
from jinja2 import Environment, FileSystemLoader

from app.domain.exceptions import DiagramRenderError

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
OUTPUT_DIR = Path(tempfile.gettempdir()) / "auto_document_generator"
IMAGES_DIR = OUTPUT_DIR / "images"

# autoescape=False karena output-nya Markdown, bukan HTML — auto-escaping
# justru akan merusak karakter Markdown biasa (*, _, |, dst).
_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)

_TEMPLATE_BY_DOC_TYPE = {
    "SDD": "sdd_template.md",
    "UAT": "uat_template.md",
}

# mermaid.ink ada di balik reverse proxy dengan batas panjang URL ~8KB.
# Diukur langsung: URL 7720 karakter masih 200, 9376 karakter sudah 414.
_MERMAID_URL_LIMIT = 8000

_HTTP_HINTS = {
    400: "script Mermaid tidak valid (cek syntax-nya)",
    414: "URL kepanjangan — script diagram terlalu besar",
    503: "layanan sedang kelebihan beban, coba lagi nanti",
}

_MANUAL_PLACEHOLDER = "*(diisi manual)*"


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


def _strip_code_fence(mermaid_script: str) -> str:
    """Buang code fence Markdown (```mermaid ... ```) kalau LLM terlanjur
    menyertakannya. Fence bikin mermaid.ink menolak script dengan HTTP 400."""
    script = mermaid_script.strip()
    if not script.startswith("```"):
        return script
    lines = [ln for ln in script.splitlines() if not ln.strip().startswith("```")]
    return "\n".join(lines).strip()


def _encode_pako(mermaid_script: str) -> str:
    """Encode script jadi segmen URL "pako:" (zlib deflate + base64url).

    mermaid.ink menerima dua bentuk: base64 polos dan "pako:" terkompresi.
    Kita pakai pako karena teks Mermaid sangat repetitif sehingga rasio
    kompresinya tinggi (~7x pada diagram nyata) — itulah yang menahan URL
    tetap di bawah batas ~8KB untuk repo besar (lihat _MERMAID_URL_LIMIT).
    """
    state = {"code": mermaid_script, "mermaid": {"theme": "default"}}
    raw = json.dumps(state, separators=(",", ":")).encode("utf-8")
    compressor = zlib.compressobj(9, zlib.DEFLATED, 15)
    deflated = compressor.compress(raw) + compressor.flush()
    return "pako:" + base64.urlsafe_b64encode(deflated).decode("ascii")


def _render_mermaid_to_image(mermaid_script: str, images_dir: Path) -> str:
    """
    Render satu script Mermaid jadi file gambar PNG lewat mermaid.ink.

    PERHATIAN: cara ini mengirim ISI DIAGRAM (bisa memuat nama endpoint,
    struktur komponen internal) ke layanan pihak ketiga lewat internet.
    Untuk data yang confidential (repo perusahaan), ganti fungsi ini
    dengan rendering lokal (mis. mermaid-cli) sebelum dipakai di
    lingkungan produksi.
    """
    images_dir.mkdir(parents=True, exist_ok=True)

    script = _strip_code_fence(mermaid_script)
    url = f"https://mermaid.ink/img/{_encode_pako(script)}"

    if len(url) > _MERMAID_URL_LIMIT:
        raise DiagramRenderError(
            f"Script diagram terlalu besar untuk mermaid.ink walau sudah dikompresi "
            f"(URL {len(url)} karakter, batas ~{_MERMAID_URL_LIMIT}). Pecah diagram "
            f"jadi beberapa bagian, atau pindah ke rendering lokal (mermaid-cli)."
        )

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        raise DiagramRenderError(
            f"mermaid.ink menolak diagram (HTTP {status}): {_HTTP_HINTS.get(status, 'sebab tidak dikenal')}."
        ) from e
    except requests.RequestException as e:
        raise DiagramRenderError(
            f"mermaid.ink tidak merespons ({type(e).__name__}). Cek koneksi internet."
        ) from e

    image_path = images_dir / f"{uuid.uuid4().hex}.png"
    image_path.write_bytes(response.content)
    return str(image_path)


def _build_sdd_context(data: dict[str, Any]) -> dict[str, Any]:
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

    return {
        **data,
        "feature_requirements": cleaned_features,
        "use_cases": cleaned_use_cases,
        "diagrams": {
            "system_architecture_image": _render_mermaid_to_image(
                diagrams["system_architecture"], IMAGES_DIR
            ),
            "component_integration_image": _render_mermaid_to_image(
                diagrams["component_integration"], IMAGES_DIR
            ),
            "use_case_diagram_image": _render_mermaid_to_image(
                diagrams["use_case_diagram"], IMAGES_DIR
            ),
            "activity_diagrams": [
                {
                    "activity_name": activity["activity_name"],
                    "description": activity["description"],
                    "image_path": _render_mermaid_to_image(
                        activity["mermaid_script"], IMAGES_DIR
                    ),
                }
                for activity in diagrams.get("activity_diagrams", [])
            ],
        },
    }


def _build_uat_context(data: dict[str, Any]) -> dict[str, Any]:
    # Ganti newline jadi "; " supaya tidak merusak baris tabel Markdown
    # (satu baris tabel Markdown wajib satu baris teks).
    cleaned_cases = [
        {**tc, "steps": tc["steps"].replace("\n", "; ")}
        for tc in data.get("uat_test_cases", [])
    ]
    return {**data, "uat_test_cases": cleaned_cases}


def generate_docx(
    document_type: str,
    document_content: dict[str, Any],
    project_name: str = "",
    document_metadata: dict[str, Any] | None = None,
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
    Mengembalikan path file .docx yang sudah jadi.
    """
    normalized_type = document_type.upper()
    template_name = _TEMPLATE_BY_DOC_TYPE.get(normalized_type)
    if template_name is None:
        raise ValueError(f"document_type tidak dikenal: {document_type!r} (harus 'SDD' atau 'UAT')")

    context = {
        "project_name": project_name,
        "meta": _build_metadata_context(document_metadata),
        **document_content,
    }

    if normalized_type == "SDD":
        context = {**context, **_build_sdd_context(document_content)}
    else:
        context = {**context, **_build_uat_context(document_content)}

    template = _jinja_env.get_template(template_name)
    rendered_markdown = template.render(**context)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{normalized_type}_{uuid.uuid4().hex}.docx"

    try:
        pypandoc.convert_text(
            rendered_markdown,
            to="docx",
            format="md",
            outputfile=str(output_path),
            extra_args=["--standalone", "--toc"],
        )
    except OSError as e:
        raise RuntimeError(
            "Pandoc tidak ditemukan di sistem. Install pandoc terlebih dahulu "
            "(https://pandoc.org/installing.html) atau jalankan "
            "`python -c \"import pypandoc; pypandoc.download_pandoc()\"` sekali."
        ) from e

    return str(output_path)
