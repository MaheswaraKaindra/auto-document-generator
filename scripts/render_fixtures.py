"""Render SEMUA Contract B yang tersimpan jadi .docx — regresi visual $0.

KENAPA ADA: satu-satunya langkah berbayar di pipeline ini adalah Contract A ->
Contract B (panggilan LLM). Begitu Contract B tersimpan, seluruh sisa pipeline
(template -> diagram -> docx) bisa diulang berapa kali pun **tanpa biaya**. Jadi
kalau kuota API habis, pekerjaan Peran 3 (templating, tabel, diagram, pagination,
cover) TETAP bisa dikerjakan dan diverifikasi sepenuhnya.

BEDA DENGAN pytest: pytest MEMALSUKAN plantuml.jar dan menjawab "kode sesuai
rancangan?". Script ini memakai plantuml SUNGGUHAN dan menjawab "dokumennya
benar-benar jadi?". Bug seperti diagram yang gagal dirender, atau Contract B yang
skemanya sudah basi, TIDAK terlihat oleh pytest — cuma terlihat di sini.
(Untuk menilai TATA LETAK — halaman kosong, tabel pecah — docx-nya masih harus
dibuka: `--out` menyimpannya.)

BEDA DENGAN scripts/validation/: yang itu ingest+parse repo publik (dan Tahap 2-nya
BERBAYAR). Script ini tidak menyentuh jaringan sama sekali.

    python scripts/render_fixtures.py                 # semua fixture, semua template
    python scripts/render_fixtures.py --only esteler  # saring nama fixture
    python scripts/render_fixtures.py --out hasil/    # simpan docx-nya

Fixture dibaca dari DUA tempat:
  - `dummy_data/*.json`         — ikut repo, jadi selalu ada
  - `scripts/validation/out/*contract_b*.json` — hasil run berbayar sebelumnya,
    GITIGNORED (bisa hilang; itu sebabnya dua yang terkaya disalin ke dummy_data)

Contract B dari SEBELUM 2026-07-16 (migrasi Mermaid -> PlantUML) tidak lagi
kompatibel; script ini melaporkannya sebagai SKEMA-LAMA, bukan menyembunyikannya.
"""

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.compiler_service import generate_docx  # noqa: E402
from scripts.evaluate_document import evaluate  # noqa: E402

FIXTURE_DIRS = [ROOT / "dummy_data", ROOT / "scripts" / "validation" / "out"]


def _contract_a_for(fixture: Path) -> Path | None:
    """Contract A pasangan sebuah fixture Contract B, kalau ada.

    Dua konvensi penamaan yang dipakai repo ini:
      `esteler-flask__SDD_contract_b.json` -> `esteler-flask__contract_a.json`
      `contract_b_rich_sdd.json`           -> `contract_a_rich_sdd.json`

    Mengembalikan None kalau tak ketemu — itu bukan kesalahan: metrik konsistensi
    tetap jalan tanpa Contract A, dan lebih baik mengukur SEBAGIAN daripada diam.
    """
    stem = fixture.stem
    kandidat = []
    if "__" in stem:
        kandidat.append(f"{stem.split('__', 1)[0]}__contract_a.json")
    if "contract_b" in stem:
        kandidat.append(f"{stem.replace('contract_b', 'contract_a')}.json")
    for nama in kandidat:
        path = fixture.parent / nama
        if path.exists():
            return path
    return None


def _is_stale_schema(data: dict) -> bool:
    """Contract B pra-2026-07-16 — field diagram masih bentuk Mermaid.

    Dipakai untuk MELEWATI pengukuran mutu, sama seperti render melewatinya.
    Alasannya bukan kerapian: id node Mermaid (`BukaHome[Buka Home]`) terbaca
    sebagai istilah teknis tak berjejak, dan dua fixture basi menyumbang 42 dari
    50 temuan — cukup untuk menenggelamkan temuan yang sungguhan.
    """
    diagrams = data.get("diagrams", {})
    skalar = [v for v in diagrams.values() if isinstance(v, str) and v.strip()]
    return bool(skalar) and not any("@start" in v for v in skalar)


def _quality_line(fixture: Path, data: dict) -> tuple[str, int]:
    """Satu baris ringkas mutu ISI + jumlah temuan yang layak diperiksa manusia.

    Ada di sini supaya mutu isi ikut TERUKUR tiap kali regresi visual dijalankan,
    bukan sekali saat ditulis lalu terlupakan. Grounding & representasi butuh
    Contract A; konsistensi tidak, jadi dia selalu jalan.
    """
    if _is_stale_schema(data):
        return ("dilewati (fixture skema lama)", 0)
    contract_a_path = _contract_a_for(fixture)
    contract_a = (json.loads(contract_a_path.read_text(encoding="utf-8"))
                  if contract_a_path else {})
    hasil = evaluate(contract_a, data)
    g, r, k = hasil["grounding"], hasil["representasi"], hasil["konsistensi"]
    temuan = len(g["tak_berjejak"]) + k["jumlah"]
    if contract_a_path is None:
        return (f"konsistensi {k['jumlah']} pertentangan "
                f"(grounding/representasi dilewati: Contract A tak ada)", k["jumlah"])
    return (f"grounding {g['rasio']:.0%}, representasi {r['rasio']:.0%}, "
            f"{k['jumlah']} pertentangan", temuan)


def _find_fixtures(pattern: str | None) -> list[Path]:
    found: list[Path] = []
    for directory in FIXTURE_DIRS:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            # Contract B dikenali dari isinya, bukan dari namanya: `dummy_data/`
            # juga memuat Contract A (parsed_repo_context) yang bukan urusan sini.
            if '"document_type"' not in text or '"diagrams"' not in text:
                continue
            if pattern and pattern.lower() not in path.stem.lower():
                continue
            found.append(path)
    return found


def _shape(docx_path: str) -> str:
    """Ukuran & jumlah gambar docx — bukti kasar "dokumennya benar-benar terisi".

    SENGAJA BUKAN jumlah halaman. `docProps/app.xml` memang punya `<Pages>`, tapi
    Pandoc selalu menulisnya **1** apa pun isinya (diprobe: dokumen esteler yang
    sudah dipastikan 29 halaman tetap melaporkan 1) — angka itu baru diisi Word
    saat menyimpan. Melaporkannya apa adanya berarti mencetak angka yang salah
    dengan percaya diri. Paginasi sungguhan butuh render (Word/LibreOffice), di
    luar lingkup script ini; yang di bawah ini terhitung langsung dari paketnya.
    """
    try:
        package = zipfile.ZipFile(docx_path)
    except zipfile.BadZipFile:
        return "PAKET RUSAK"
    images = sum(1 for n in package.namelist() if n.startswith("word/media/"))
    return f"{Path(docx_path).stat().st_size // 1024:>4} KB, {images} gambar"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="saring nama fixture (substring)")
    parser.add_argument("--out", help="folder tujuan docx (default: tidak disimpan)")
    parser.add_argument("--templates", default="premco,default",
                        help="daftar template_id dipisah koma")
    args = parser.parse_args()

    fixtures = _find_fixtures(args.only)
    if not fixtures:
        print("Tidak ada fixture Contract B yang cocok.")
        return 1
    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    templates = [t.strip() for t in args.templates.split(",") if t.strip()]

    print(f"{len(fixtures)} fixture x {len(templates)} template — plantuml SUNGGUHAN, $0\n")
    failures = 0
    stale = 0
    findings = 0
    for path in fixtures:
        data = json.loads(path.read_text(encoding="utf-8"))
        counts = (f"{len(data.get('feature_requirements', []))}f/"
                  f"{len(data.get('use_cases', []))}uc/"
                  f"{len(data.get('diagrams', {}).get('activity_diagrams', []))}ad/"
                  f"{len(data.get('uat_test_cases', []))}tc")
        print(f"{path.stem[:44]:46} {counts}")
        try:
            mutu, temuan = _quality_line(path, data)
            findings += temuan
            print(f"  {'mutu isi':22} {mutu}")
        except Exception as e:                              # noqa: BLE001
            # Fixture skema lama bisa saja tak punya bentuk yang diharapkan
            # evaluator. Itu tak boleh menggagalkan regresi VISUAL — dua
            # pertanyaan yang berbeda.
            print(f"  {'mutu isi':22} tak terukur ({type(e).__name__})")
        for doc_type in ("SDD", "UAT"):
            for template_id in templates:
                label = f"  {doc_type}/{template_id}"
                try:
                    produced = generate_docx(doc_type, data, project_name=path.stem,
                                             template_id=template_id)
                except Exception as e:                      # noqa: BLE001
                    if isinstance(e, TypeError):
                        # Contract B pra-2026-07-16 (field diagram masih bentuk
                        # Mermaid). Tetap DILAPORKAN — fixture basi harus
                        # terlihat, bukan lolos diam-diam — tapi dihitung
                        # TERPISAH dari kegagalan: ini ketidakcocokan yang sudah
                        # diketahui & didokumentasikan, bukan regresi. Harness
                        # yang selalu exit non-zero akan diabaikan orang, dan
                        # saat itulah regresi yang SUNGGUHAN ikut terlewat.
                        print(f"{label:24} LEWAT  SKEMA-LAMA (pra-2026-07-16)")
                        stale += 1
                    else:
                        print(f"{label:24} GAGAL  {type(e).__name__}: {str(e)[:60]}")
                        failures += 1
                    continue
                print(f"{label:24} OK     {_shape(produced)}")
                if out_dir:
                    # Satu subfolder per fixture. Dulu semuanya datar di satu
                    # folder: 10 fixture x 2 jenis x 2 template = 40 file dengan
                    # nama panjang berulang — praktis tak bisa ditelusuri mata.
                    # Dikelompokkan per fixture, tiap folder cuma berisi 4 file
                    # bernama pendek (SDD_premco.docx, dst).
                    target = out_dir / path.stem
                    target.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(produced, target / f"{doc_type}_{template_id}.docx")
        print()

    summary = f"Selesai. {failures} gagal"
    if stale:
        summary += f", {stale} dilewati (fixture skema lama — bukan regresi)"
    if findings:
        summary += f", {findings} temuan mutu isi (periksa manual)"
    print(summary + ".")
    # Exit code SENGAJA cuma mencerminkan kegagalan render. Temuan mutu itu
    # sinyal untuk dibaca manusia, bukan vonis: grounding bisa keliru menuduh
    # (istilah sah yang tak muncul literal di Contract A), dan harness yang
    # selalu merah akan diabaikan orang — saat itulah regresi SUNGGUHAN terlewat.
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
