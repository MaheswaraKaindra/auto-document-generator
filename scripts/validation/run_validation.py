"""
Harness validasi: jalankan pipeline terhadap repo publik nyata yang beragam.

Ini BUKAN pengganti pytest. pytest menjawab "apakah kode melakukan yang kita
rancang?" (mock, gratis, 4 detik). Harness ini menjawab pertanyaan yang berbeda:
"apakah rancangan kita bertahan di repo yang belum pernah kita lihat?"

Bedanya nyata: bug 414 mermaid.ink lolos dari 11 test yang semuanya hijau,
karena mermaid.ink di-mock. Bug itu hanya muncul di repo sungguhan.

DUA TAHAP, sengaja dipisah berdasarkan BIAYA
--------------------------------------------
  Tahap 1 (default, GRATIS)
      ingest -> parse. Tidak menyentuh LLM sama sekali. Sudah cukup untuk
      menjawab "apakah parser paham repo ini?" — lewat metrik `coverage`.
      Contract A disimpan ke disk supaya Tahap 2 tidak perlu ingest ulang.

  Tahap 2 (--with-llm, BERBAYAR)
      Contract A -> LLM -> docx. SATU repo = SATU panggilan Claude berbayar.
      Wajib opt-in eksplisit. Baca dulu laporan Tahap 1, baru pilih sedikit
      kasus yang memang layak dibayari.

Alur yang disarankan: jalankan Tahap 1 ke semua kasus, baca laporannya, lalu
Tahap 2 hanya ke 2-3 kasus yang paling informatif.

Contoh
------
    # Tahap 1, semua kasus (gratis)
    python scripts/validation/run_validation.py

    # Tahap 1, kasus tertentu saja
    python scripts/validation/run_validation.py --only flask gin-go

    # Tahap 2 (BERBAYAR) — pakai Contract A yang sudah tersimpan
    python scripts/validation/run_validation.py --only flask --with-llm

Catatan rate limit: tanpa GITHUB_TOKEN, GitHub cuma memberi 60 request/jam dan
harness ini akan kehabisan jatah di tengah jalan. Isi GITHUB_TOKEN di .env
sebelum menjalankan banyak kasus sekaligus.
"""

import argparse
import json
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from app.core import config  # noqa: E402
from app.domain.models import GithubIngestRequest, SourceType  # noqa: E402
from app.services.compiler_service import generate_docx  # noqa: E402
from app.services.ingestion_service import IngestionService  # noqa: E402
# Cuma fungsi serialisasinya, BUKAN LLMService — yang itu tetap di-import tertunda
# di dalam run_stage2 supaya Tahap 1 tidak pernah membuat client Anthropic.
# format_contract_a tidak menyentuh jaringan maupun API key.
from app.services.llm_service import format_contract_a  # noqa: E402
from app.services.parser_service import build_parsed_repo_context  # noqa: E402

CASES_FILE = Path(__file__).parent / "repos.json"
OUT_DIR = Path(__file__).parent / "out"


def _load_cases() -> list[dict]:
    return json.loads(CASES_FILE.read_text(encoding="utf-8"))["cases"]


def _github_quota() -> tuple[int, int, str]:
    """Sisa jatah GitHub API: (remaining, limit, waktu reset)."""
    from github import Auth, Github

    client = Github(auth=Auth.Token(config.GITHUB_TOKEN)) if config.GITHUB_TOKEN else Github()
    rate_limit = client.get_rate_limit()
    core = rate_limit.core if hasattr(rate_limit, "core") else rate_limit.resources.core
    return core.remaining, core.limit, str(core.reset)


# Per repo: get_repo + get_archive_link, plus margin. Unduhan tarball-nya sendiri
# lewat codeload dan TIDAK memotong jatah — itulah sebabnya angkanya sekecil ini.
_API_REQUESTS_PER_REPO = 3


def _preflight(cases: list[dict]) -> bool:
    """Cek jatah API SEBELUM mulai.

    Tanpa ini, jatah yang habis tidak muncul sebagai error jelas — ingestion
    cuma menggantung lalu gagal dengan sebab yang tidak kelihatan. Lebih baik
    menolak jalan dalam sedetik.

    Ambangnya dihitung dari jumlah repo yang akan diproses, bukan angka mati.
    Versi pertama harness ini memakai ambang mati 50 — warisan dari zaman
    ingestion masih 1 request per file — dan langsung basi begitu ingestion
    pindah ke tarball: sisa 45 ditolak padahal cukup untuk 20-an repo.
    """
    repo_count = sum(len(c["repos"]) for c in cases)
    needed = repo_count * _API_REQUESTS_PER_REPO
    remaining, limit, reset = _github_quota()

    print(f"Jatah GitHub API: {remaining}/{limit} (butuh ~{needed}, reset {reset})")

    if remaining < needed:
        print(
            f"BERHENTI: sisa jatah {remaining} tidak cukup untuk {repo_count} repo "
            f"(butuh ~{needed}).\n"
            f"          Tunggu sampai {reset}, isi GITHUB_TOKEN di .env, atau "
            f"persempit dengan --only.",
            file=sys.stderr,
        )
        return False

    if not config.GITHUB_TOKEN:
        print(
            "GITHUB_TOKEN kosong -> batas anonim 60 request/jam. Cukup untuk daftar\n"
            "ini karena tarball cuma makan ~3 request/repo, tapi isi token kalau mau\n"
            "sering menjalankannya (batas naik jadi 5.000/jam).\n"
        )
    return True


def _summarize(context: dict) -> dict:
    """Ringkas Contract A jadi angka-angka yang bisa dibandingkan antar repo.

    `coverage` adalah metrik utamanya: porsi file yang berhasil dikenali tipenya
    (controller/service/model/ui_component) versus yang jatuh ke fallback
    "other". Coverage rendah = LLM cuma dapat nama file tanpa struktur, jadi
    dokumen apa pun yang dihasilkan patut dicurigai karangan.

    Ini semua dihitung TANPA memanggil LLM — itulah kenapa Tahap 1 gratis tapi
    tetap informatif.
    """
    files = [f for repo in context["repositories"] for f in repo["files"]]
    total = len(files)
    types = Counter(f["type"] for f in files)
    other = types.get("other", 0)

    return {
        "files": total,
        "coverage": round((total - other) / total, 3) if total else 0.0,
        "by_type": dict(types.most_common()),
        "endpoints": sum(len(f.get("api_endpoints", [])) for f in files),
        "classes": sum(len(f.get("classes", [])) for f in files),
        "functions": sum(len(f.get("functions", [])) for f in files),
        # format_contract_a() dari llm_service, BUKAN json.dumps() sendiri: harness
        # ini dulu mengukur bentuk compact sementara llm_service mengirim indent=2,
        # jadi laporannya meleset 21-25% dan menyesatkan tiap keputusan yang
        # bersandar padanya (medusa dilaporkan 2.831 KB; yang dikirim 1,58 juta
        # token). Alat ukur yang tidak mengukur benda yang dikirim itu lebih buruk
        # daripada tidak mengukur sama sekali — dia memberi rasa aman palsu.
        "contract_a_kb": round(len(format_contract_a(context).encode("utf-8")) / 1024, 1),
    }


def _contract_a_path(case_name: str) -> Path:
    return OUT_DIR / f"{case_name}__contract_a.json"


def run_stage1(case: dict) -> dict:
    """Ingest + parse. Gratis — tidak memanggil LLM."""
    started = time.monotonic()
    requests = [
        GithubIngestRequest(
            repo_tag=r["repo_tag"],
            repo_url=r["repo_url"],
            access_token=config.GITHUB_TOKEN or None,
        )
        for r in case["repos"]
    ]

    workspaces = IngestionService().ingest(SourceType.GITHUB, requests)
    context = build_parsed_repo_context(project_name=case["name"], workspaces=workspaces)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _contract_a_path(case["name"]).write_text(
        json.dumps(context, indent=2), encoding="utf-8"
    )

    result = _summarize(context)
    result["seconds"] = round(time.monotonic() - started, 1)
    return result


def run_stage2(case: dict, doc_type: str) -> dict:
    """Contract A -> LLM -> docx. BERBAYAR: satu panggilan Claude per kasus."""
    from app.services.llm_service import LLMService

    path = _contract_a_path(case["name"])
    if not path.exists():
        raise FileNotFoundError(
            f"Contract A untuk '{case['name']}' belum ada. Jalankan Tahap 1 dulu "
            f"(tanpa --with-llm) supaya panggilan berbayar tidak terbuang percuma."
        )

    started = time.monotonic()
    context = json.loads(path.read_text(encoding="utf-8"))
    content = LLMService().generate_document_content(
        parsed_repo_context=context, target_doc_type=doc_type
    )

    # Simpan Contract B mentahnya, bukan cuma docx-nya. Menilai kualitas berarti
    # membaca narasi yang ditulis LLM, dan membaca JSON jauh lebih enak daripada
    # membongkar docx. Ini juga bikin hasil panggilan berbayar bisa diperiksa
    # ulang berkali-kali tanpa membayar lagi.
    (OUT_DIR / f"{case['name']}__{doc_type}_contract_b.json").write_text(
        json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    docx_path = generate_docx(doc_type, content, project_name=case["name"])
    out_docx = OUT_DIR / f"{case['name']}__{doc_type}.docx"
    out_docx.write_bytes(Path(docx_path).read_bytes())

    return {
        "seconds": round(time.monotonic() - started, 1),
        "docx": str(out_docx),
        "docx_kb": round(out_docx.stat().st_size / 1024, 1),
        # Angka-angka ini yang menunjukkan apakah target_doc_type benar-benar
        # menggeser kedalaman konten, bukan cuma mengganti label.
        "use_cases": len(content.get("use_cases", [])),
        "features": len(content.get("feature_requirements", [])),
        "uat_test_cases": len(content.get("uat_test_cases", [])),
        "activity_diagrams": len(content.get("diagrams", {}).get("activity_diagrams", [])),
    }


def _print_report(results: list[dict], with_llm: bool) -> None:
    print("\n" + "=" * 78)
    print("LAPORAN VALIDASI")
    print("=" * 78)

    for r in results:
        status = "GAGAL" if r.get("error") else "ok"
        print(f"\n[{status}] {r['name']}")
        print(f"  asumsi : {r['asumsi_yang_diuji']}")

        if r.get("error"):
            print(f"  ERROR  : {r['error']}")
            continue

        s1 = r["stage1"]
        print(
            f"  parse  : {s1['files']} file, coverage {s1['coverage']:.0%}, "
            f"{s1['endpoints']} endpoint, {s1['classes']} class, "
            f"{s1['functions']} function ({s1['seconds']}s, Contract A {s1['contract_a_kb']} KB)"
        )
        print(f"  tipe   : {s1['by_type']}")

        if with_llm and r.get("stage2"):
            s2 = r["stage2"]
            print(
                f"  dokumen: {s2['features']} fitur, {s2['use_cases']} use case, "
                f"{s2['uat_test_cases']} test case, {s2['activity_diagrams']} activity diagram "
                f"({s2['seconds']}s)"
            )
            print(f"  file   : {s2['docx']} ({s2['docx_kb']} KB)")

    print("\n" + "-" * 78)
    print("Coverage rendah = parser cuma lihat nama file, tanpa struktur. Dokumen")
    print("yang lahir dari situ patut dicurigai karangan meski terbaca meyakinkan.")
    if with_llm:
        print("\nAngka di atas TIDAK bisa menilai apakah dokumennya bagus. Buka .docx-nya")
        print("dan baca sendiri — itu bagian yang memang tidak bisa diotomatiskan.")
    else:
        print("\nIni Tahap 1 (gratis). Untuk menilai kualitas dokumen, pilih beberapa")
        print("kasus lalu jalankan ulang dengan --with-llm.")
    print("-" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validasi pipeline terhadap repo publik nyata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--only", nargs="+", metavar="NAMA", help="Jalankan kasus tertentu saja.")
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help="BERBAYAR: lanjut ke LLM + docx. Satu kasus = satu panggilan Claude.",
    )
    parser.add_argument("--doc-type", choices=["SDD", "UAT"], default="SDD")
    parser.add_argument("--list", action="store_true", help="Tampilkan daftar kasus lalu keluar.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Lewati konfirmasi interaktif untuk --with-llm. WAJIB di shell "
        "non-interaktif: tanpa ini input() menunggu jawaban yang tidak akan "
        "pernah datang — terjadi betulan (proses idle 30+ menit, nol panggilan "
        "API, disangka regen lambat).",
    )
    args = parser.parse_args()

    cases = _load_cases()
    if args.list:
        for c in cases:
            repos = ", ".join(r["repo_url"].split("github.com/")[-1] for r in c["repos"])
            print(f"{c['name']:26} {repos}")
        return 0

    if args.only:
        known = {c["name"] for c in cases}
        unknown = set(args.only) - known
        if unknown:
            print(f"Kasus tidak dikenal: {', '.join(sorted(unknown))}", file=sys.stderr)
            print(f"Tersedia: {', '.join(sorted(known))}", file=sys.stderr)
            return 2
        cases = [c for c in cases if c["name"] in args.only]

    if not _preflight(cases):
        return 2

    if args.with_llm:
        print(
            f"BERBAYAR: {len(cases)} kasus x 1 panggilan Claude ({args.doc_type}).\n"
            f"          Repo besar bisa makan waktu beberapa menit per kasus.\n"
        )
        if not args.yes and input("Lanjut? [y/N] ").strip().lower() != "y":
            print("Dibatalkan.")
            return 1

    results = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['name']} ... ", end="", flush=True)
        record = {"name": case["name"], "asumsi_yang_diuji": case["asumsi_yang_diuji"]}
        try:
            record["stage1"] = run_stage1(case)
            print(f"parse ok (coverage {record['stage1']['coverage']:.0%})", end="", flush=True)
            if args.with_llm:
                print(" ... LLM ... ", end="", flush=True)
                record["stage2"] = run_stage2(case, args.doc_type)
                print("dokumen ok")
            else:
                print()
        except Exception as e:
            # Sengaja menangkap semua: satu repo yang meledak tidak boleh
            # menghentikan validasi repo lain — justru ledakannya itu datanya.
            record["error"] = f"{type(e).__name__}: {e}"
            record["traceback"] = traceback.format_exc()
            print(f"GAGAL ({type(e).__name__})")

        results.append(record)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUT_DIR / "report.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    _print_report(results, args.with_llm)
    print(f"\nLaporan lengkap (termasuk traceback): {report_path}")

    return 1 if any(r.get("error") for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
