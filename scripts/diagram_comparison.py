"""Lembar perbandingan bahasa diagram: Mermaid (sekarang) vs PlantUML vs D2.

Alat bantu KEPUTUSAN PRODUK, bukan bagian aplikasi. Konteks (2026-07-16):
pemilik project menilai hasil Mermaid "masih sedikit kurang memuaskan", dan
dokumen acuan enterprise memakai diagram bergaya UML (aktor stick-figure di
use case, activity diagram ber-start/end). Script ini merender diagram YANG
SAMA — diambil dari Contract B esteler yang tersimpan, bukan dikarang — dalam
tiga bahasa, lalu menyusunnya berdampingan dalam satu halaman HTML supaya
keputusannya dibuat dengan MATA, bukan dengan reputasi tools.

Terjemahan PlantUML/D2 di bawah ditulis TANGAN (bukan LLM) — sengaja, supaya
yang dinilai murni kemampuan RENDER-nya; kemampuan LLM menulis bahasa itu
diuji terpisah nanti kalau bahasanya terpilih.

PlantUML & D2 dirender LOKAL — isi diagram tidak meninggalkan mesin ini.
(Rencana awal memakai kroki.io ditolak guard keamanan, dan penolakan itu
benar: mengirim struktur aplikasi anggota tim ke layanan pihak ketiga baru
bukan keputusan yang boleh diambil sepihak. Sisi Mermaid tetap lewat
mermaid.ink karena itu persis jalur produk saat ini — kirimannya bukan baru.)

Prasyarat (unduh sekali, taruh di mana saja, tunjuk lewat env var):
  - Java 17+ di PATH
  - PLANTUML_JAR = path ke plantuml.jar   (github.com/plantuml/plantuml/releases)
  - D2_EXE       = path ke d2.exe          (github.com/terrastruct/d2/releases)

KEPUTUSANNYA SUDAH DIAMBIL (2026-07-16): pemilik project memilih PlantUML, dan
produk sudah dimigrasikan — compiler_service kini merender PlantUML lokal.
Script ini disimpan sebagai REKAM JEJAK bagaimana keputusan itu dibuat; sisi
Mermaid-nya kini self-contained (encoding pako + mermaid.ink inline) karena
fungsi mermaid di compiler_service sudah tidak ada.

Pakai:  python scripts/diagram_comparison.py
Hasil:  scripts/validation/out/diagram_comparison.html  (buka di browser)
Biaya:  $0 — nol panggilan LLM.
"""

import base64
import json
import os
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "scripts" / "validation" / "out"
CONTRACT_B = OUT_DIR / "esteler-flask__SDD_contract_b.json"
HTML_OUT = OUT_DIR / "diagram_comparison.html"

PLANTUML_JAR = os.environ.get("PLANTUML_JAR", "")
D2_EXE = os.environ.get("D2_EXE", "")

# ---------------------------------------------------------------------------
# Terjemahan tangan dari script Mermaid di Contract B esteler.
# Isinya (aktor, use case, langkah, cabang, loop) SAMA — cuma bahasanya beda.
# ---------------------------------------------------------------------------

USE_CASE_PLANTUML = """@startuml
!theme plain
left to right direction
actor Admin
actor Customer
rectangle "Esteler App" {
  usecase "Login ke Sistem" as UC1
  usecase "Mengelola Menu" as UC2
  usecase "Mengelola Pesanan" as UC3
  usecase "Melihat Dashboard & Laporan" as UC4
  usecase "Membuat Pesanan Walk-in" as UC5
  usecase "Menjelajahi Menu" as UC6
  usecase "Mengelola Keranjang Belanja" as UC7
  usecase "Melakukan Checkout Pesanan" as UC8
  usecase "Melacak Status Pesanan" as UC9
  usecase "Memberikan Rating" as UC10
  usecase "Chat dengan Asisten AI" as UC11
}
Admin --> UC1
Admin --> UC2
Admin --> UC3
Admin --> UC4
Admin --> UC5
Customer --> UC6
Customer --> UC7
Customer --> UC8
Customer --> UC9
Customer --> UC10
Customer --> UC11
@enduml
"""

ACTIVITY_PLANTUML = """@startuml
!theme plain
start
repeat :Buka Keranjang;
  :Isi Data Preorder;
  :Submit Checkout;
backward :Tampilkan Pesan Keranjang Kosong;
repeat while (Keranjang Kosong?) is (Ya) not (Tidak)
:Buat Order (ONLINE_PREORDER);
:Tampilkan Kode Pesanan;
:Arahkan ke Halaman Pembayaran;
stop
@enduml
"""

ARCH_D2 = """direction: right
user: User { shape: person }
browser: "Web Browser\\n(UI Templates)"
backend: "Flask Backend Application"
db: "PostgreSQL Database" { shape: cylinder }
cloudinary: "Cloudinary\\n(Image Storage)"
groq: "Groq AI Service\\n(Chatbot)"
user -> browser
browser -> backend
backend -> db
backend -> cloudinary
backend -> groq
"""

ARCH_PLANTUML = """@startuml
!theme plain
left to right direction
actor User
component "Web Browser\\n(UI Templates)" as Browser
component "Flask Backend\\nApplication" as Backend
database "PostgreSQL\\nDatabase" as DB
cloud "Cloudinary\\n(Image Storage)" as Cloudinary
cloud "Groq AI Service\\n(Chatbot)" as Groq
User --> Browser
Browser --> Backend
Backend --> DB
Backend --> Cloudinary
Backend --> Groq
@enduml
"""


def render_plantuml(source: str) -> tuple[bytes, str]:
    """Render lokal via plantuml.jar (mode -pipe: stdin -> PNG di stdout).

    -Playout=smetana: layout engine Java murni bawaan PlantUML — tanpa ini,
    diagram use case & component menuntut Graphviz/dot terpasang di sistem."""
    result = subprocess.run(
        ["java", "-jar", PLANTUML_JAR, "-pipe", "-tpng",
         "-charset", "UTF-8", "-Playout=smetana"],
        input=source.encode("utf-8"),
        capture_output=True,
        timeout=120,
    )
    if result.returncode != 0 or not result.stdout.startswith(b"\x89PNG"):
        raise RuntimeError(f"plantuml gagal: {result.stderr.decode(errors='replace')[:500]}")
    return result.stdout, "image/png"


def render_d2(source: str) -> tuple[bytes, str]:
    """Render lokal via d2.exe. Output SVG — ekspor PNG di d2 butuh headless
    browser, sementara SVG native dan browser menampilkannya sama baiknya."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "diagram.d2"
        dst = Path(tmp) / "diagram.svg"
        src.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [D2_EXE, str(src), str(dst)],
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"d2 gagal: {result.stderr.decode(errors='replace')[:500]}")
        return dst.read_bytes(), "image/svg+xml"


def render_mermaid(script: str) -> tuple[bytes, str]:
    """Render lewat mermaid.ink (jalur produk LAMA, sebelum migrasi PlantUML) —
    inline di sini karena fungsinya sudah dihapus dari compiler_service."""
    state = {"code": script, "mermaid": {"theme": "default"}}
    raw = json.dumps(state, separators=(",", ":")).encode("utf-8")
    compressor = zlib.compressobj(9, zlib.DEFLATED, 15)
    deflated = compressor.compress(raw) + compressor.flush()
    encoded = "pako:" + base64.urlsafe_b64encode(deflated).decode("ascii")
    resp = requests.get(
        f"https://mermaid.ink/img/{encoded}?type=png&width=1600", timeout=30
    )
    resp.raise_for_status()
    return resp.content, "image/png"


def data_uri(content: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(content).decode()}"


def main() -> None:
    missing = [name for name, val in
               [("PLANTUML_JAR", PLANTUML_JAR), ("D2_EXE", D2_EXE)]
               if not val or not Path(val).exists()]
    if missing:
        sys.exit(f"env var belum menunjuk file yang ada: {', '.join(missing)} — "
                 "lihat docstring untuk cara mengunduh toolnya")

    contract_b = json.loads(CONTRACT_B.read_text(encoding="utf-8"))
    diagrams = contract_b["diagrams"]
    checkout = next(
        a for a in diagrams["activity_diagrams"] if "Checkout" in a["activity_name"]
    )

    sections = [
        (
            "Use Case Diagram",
            "Aktor & use case identik; acuan enterprise memakai gaya UML "
            "(stick-figure + oval + kotak sistem).",
            [
                ("Mermaid — dipakai produk SEKARANG",
                 lambda: render_mermaid(diagrams["use_case_diagram"])),
                ("PlantUML — UML sungguhan",
                 lambda: render_plantuml(USE_CASE_PLANTUML)),
            ],
        ),
        (
            "Activity Diagram — Checkout dan Pembuatan Pesanan Online",
            "Langkah, cabang keputusan, dan loop kembali-ke-keranjang identik.",
            [
                ("Mermaid — dipakai produk SEKARANG",
                 lambda: render_mermaid(checkout["mermaid_script"])),
                ("PlantUML — activity UML (start/stop/diamond)",
                 lambda: render_plantuml(ACTIVITY_PLANTUML)),
            ],
        ),
        (
            "System Architecture",
            "Komponen & panah identik (semua berjejak di Contract A).",
            [
                ("Mermaid — dipakai produk SEKARANG",
                 lambda: render_mermaid(diagrams["system_architecture"])),
                ("D2 — kotak-panah modern",
                 lambda: render_d2(ARCH_D2)),
                ("PlantUML — component diagram",
                 lambda: render_plantuml(ARCH_PLANTUML)),
            ],
        ),
    ]

    cards_html = []
    for title, note, variants in sections:
        figures = []
        for label, fn in variants:
            print(f"render: {title} / {label} ...")
            content, mime = fn()
            figures.append(
                f'<figure><img src="{data_uri(content, mime)}" alt="{label}">'
                f"<figcaption>{label}</figcaption></figure>"
            )
        cards_html.append(
            f"<section><h2>{title}</h2><p>{note}</p>"
            f'<div class="row">{"".join(figures)}</div></section>'
        )

    html = f"""<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<title>Perbandingan Bahasa Diagram — esteler (Contract B tersimpan)</title>
<style>
  body {{ font-family: Georgia, serif; margin: 2rem auto; max-width: 1400px;
         color: #1a1a1a; background: #fafaf7; }}
  h1 {{ border-bottom: 3px solid #1a1a1a; padding-bottom: .3rem; }}
  section {{ margin: 3rem 0; }}
  .row {{ display: flex; gap: 1.5rem; flex-wrap: wrap; align-items: flex-start; }}
  figure {{ margin: 0; flex: 1 1 380px; background: #fff; border: 1px solid #ccc;
            padding: 1rem; }}
  figure img {{ max-width: 100%; height: auto; max-height: 640px;
                object-fit: contain; }}
  figcaption {{ margin-top: .6rem; font-size: .95rem; font-style: italic; }}
  .catatan {{ background: #fff; border-left: 4px solid #1a1a1a; padding: 1rem;
              font-size: .95rem; }}
</style></head><body>
<h1>Perbandingan Bahasa Diagram</h1>
<p>Diagram yang sama (dari Contract B esteler tersimpan — bukan dikarang),
dirender tiga bahasa. Terjemahan ditulis tangan supaya yang dinilai murni
kemampuan <em>render</em>. PlantUML &amp; D2 dirender lokal; Mermaid lewat
mermaid.ink (jalur produk). Biaya pembuatan halaman ini: $0, nol panggilan LLM.</p>
<div class="catatan"><strong>Cara menilai:</strong> bayangkan tiap gambar di
dalam dokumen SDD resmi yang dikirim ke klien. Mana yang paling terlihat
seperti dokumen acuan enterprise? Perhatikan: aktor, bentuk node keputusan,
kepadatan teks, dan apakah diagramnya "serius".</div>
{"".join(cards_html)}
</body></html>"""

    HTML_OUT.write_text(html, encoding="utf-8")
    print(f"\nselesai -> {HTML_OUT}")


if __name__ == "__main__":
    main()
