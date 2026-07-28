"""Evaluasi ISI dokumen terhadap Contract A — menghasilkan ANGKA, bukan kesan.

Kenapa ada: `pytest` membuktikan STRUKTUR dokumen benar, `scripts/validation/`
membuktikan parser paham repo. Tak satu pun menjawab "apakah ISI dokumennya
benar". Script ini mengisi celah itu untuk bagian yang bisa dibuktikan mesin.

TIGA METRIK, tiga titik buta yang berbeda:

  1. GROUNDING  — berapa persen istilah teknis di dokumen punya jejak di
     Contract A. Menangkap KARANGAN (entitas yang tak ada di repo mana pun).

  2. REPRESENTASI — berapa persen endpoint di Contract A tersinggung di dokumen.
     Menangkap KELALAIAN (fitur yang ada di kode tapi tak masuk dokumen) — arah
     kebalikan dari grounding, dan justru yang paling gampang terlewat.

  3. KONSISTENSI — apakah `steps` sebuah aktivitas menceritakan alur yang sama
     dengan `diagram_script`-nya, dan `business_flow_steps` dengan diagramnya.
     Menangkap dokumen yang BERTENTANGAN DENGAN DIRINYA SENDIRI.

BATAS YANG HARUS DIINGAT — grounding TIDAK membuktikan "benar", cuma "tidak
dikarang". Preseden nyata di project ini: dokumen fastapi menulis fitur
"Manajemen Hero", dan pemeriksa jejak akan MELULUSKANNYA — "Hero" memang ada di
repo, tapi di `docs_src/` (folder tutorial), bukan di produknya. Salah-sumber
lolos dari metrik mana pun di sini. Akurasi semantik tetap butuh manusia yang
membaca kode; script ini mempersempit apa yang harus dibaca manusia, bukan
menggantikannya.

Pakai:
    python scripts/evaluate_document.py <contract_a.json> <contract_b.json>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Istilah yang "teknis" dan layak dituntut punya jejak: CamelCase (AuthService),
# snake_case ber-underscore (session_id), dan nama ber-titik (cloudinary.uploader).
# Kata Indonesia/Inggris biasa sengaja TIDAK diaudit — menuntut "pesanan" punya
# jejak literal di kode itu salah kaprah dan cuma melahirkan derau.
_TECH_TERM = re.compile(r"\b(?:[A-Z][a-z]+(?:[A-Z][a-z]+)+|\w+_\w+|\w+\.\w+)\b")
# Kata yang lolos regex tapi bukan istilah repo — dibuang supaya laporan bersih.
_STOP = {"session_id", "id"}

# Alias PlantUML (`[pages/index.vue] as FeHome`) itu MESIN diagram, bukan klaim
# tentang repo — yang mengklaim adalah labelnya (`pages/index.vue`), dan label itu
# tetap diaudit. Tanpa pengecualian ini satu diagram menyumbang puluhan tuduhan
# palsu: pada MyPertamina, 47 dari 48 istilah "tak berjejak" ternyata alias.
_PLANTUML_ALIAS = re.compile(r"\bas\s+([A-Za-z_]\w*)")

# Bahasa & runtime disimpulkan dari EKSTENSI FILE, bukan disebut namanya di kode.
# Contract A sebuah repo Vue tak pernah memuat kata "typescript", tapi 8 file
# `.ts`-nya adalah bukti sah — tanpa jembatan ini metrik menuduh dokumen yang
# justru benar. Kelas kesalahan yang sama dengan kasus "Neon" dulu: bukti ada di
# tempat yang tidak digeledah.
_EXT_EVIDENCE = {
    ".py": "python", ".ts": "typescript", ".tsx": "typescript react",
    ".js": "javascript node", ".jsx": "javascript react", ".vue": "vue",
    ".java": "java", ".go": "go", ".kt": "kotlin", ".cs": "c#", ".rb": "ruby",
    ".php": "php", ".rs": "rust", ".swift": "swift",
}


def _doc_text(contract_b: dict) -> str:
    """Seluruh teks yang benar-benar sampai ke pembaca dokumen."""
    parts: list[str] = []

    def walk(node):
        if isinstance(node, str):
            parts.append(node)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(contract_b)
    return "\n".join(parts)


def _evidence(contract_a: dict) -> str:
    """Seluruh bukti yang sah dari Contract A — teks mentahnya PLUS fakta turunan.

    Contract A digeledah UTUH (json.dumps), bukan per-field: docstring yang
    tersimpan di `functions[].description` juga bukti sah. Pelajaran mahal di
    project ini — "Neon" pernah dituduh karangan padahal ada di docstring,
    gara-gara yang digeledah cuma `dependencies`.

    Ditambah bahasa/runtime yang disimpulkan dari ekstensi file: sebuah repo
    tidak menuliskan kata "typescript" di mana pun, tapi file `.ts`-nya adalah
    bukti — dan tanpa jembatan itu metrik menuduh dokumen yang justru benar.
    """
    blob = json.dumps(contract_a, ensure_ascii=False).lower()
    extensions = {ext for ext in _EXT_EVIDENCE if f"{ext}\"" in blob or f"{ext}'" in blob}
    return blob + " " + " ".join(_EXT_EVIDENCE[ext] for ext in extensions)


def _grounded(term: str, evidence: str) -> bool:
    """Sebuah istilah berjejak kalau muncul utuh, ATAU pangkalnya muncul.

    Pangkal untuk nama bertitik: "Node.js" -> "node", "cloudinary.uploader" ->
    "cloudinary". Repo memang jarang menuliskan akhiran `.js`, sementara paket
    dan folder-nya memakai nama pangkalnya.
    """
    lowered = term.lower()
    if lowered in evidence:
        return True
    root = lowered.split(".")[0]
    return len(root) > 3 and root in evidence


def grounding(contract_a: dict, contract_b: dict) -> dict:
    """Metrik 1 — istilah teknis di dokumen yang TAK punya jejak di Contract A."""
    blob = _evidence(contract_a)
    aliases = {a.lower() for a in _PLANTUML_ALIAS.findall(_doc_text(contract_b))}
    terms = {t for t in _TECH_TERM.findall(_doc_text(contract_b))
             if t.lower() not in _STOP and t.lower() not in aliases}
    ungrounded = sorted(t for t in terms if not _grounded(t, blob))
    total = len(terms)
    return {
        "total_istilah": total,
        "berjejak": total - len(ungrounded),
        "tak_berjejak": ungrounded,
        "rasio": round((total - len(ungrounded)) / total, 3) if total else 1.0,
    }


def representation(contract_a: dict, contract_b: dict) -> dict:
    """Metrik 2 — endpoint di Contract A yang TIDAK tersinggung di dokumen.

    Endpoint tak pernah muncul verbatim di prosa, jadi yang dicocokkan adalah
    segmen bermaknanya (`/api/menu/<id>` -> "menu"). Kasar tapi jujur: kalau tak
    satu pun segmen sebuah endpoint muncul, area itu memang tak diceritakan.
    """
    text = _doc_text(contract_b).lower()
    endpoints, missing = [], []
    for repo in contract_a.get("repositories", []):
        for f in repo.get("files", []):
            for ep in f.get("api_endpoints", []):
                path = ep.get("path", "")
                endpoints.append(path)
                segments = [s for s in re.split(r"[/<>{}:.-]", path)
                            if s and not s.isdigit() and len(s) > 3
                            and s.lower() not in {"api", "http", "https"}]
                if segments and not any(s.lower() in text for s in segments):
                    missing.append(path)
    total = len(endpoints)
    return {
        "total_endpoint": total,
        "tersinggung": total - len(missing),
        "tak_tersinggung": sorted(set(missing)),
        "rasio": round((total - len(missing)) / total, 3) if total else 1.0,
    }


_WORD = re.compile(r"\w{4,}")


def _covered(action: str, steps: list[str]) -> bool:
    """Apakah satu aksi diagram diceritakan oleh salah satu langkah teks?

    Diukur dari tumpang-tindih kata bermakna (>=2 kata sama), BUKAN dari
    kecocokan persis: teks dokumen memang meringkas, dan itu sah.
    """
    words = set(_WORD.findall(action.lower()))
    return any(len(words & set(_WORD.findall(s.lower()))) >= 2 for s in steps)


def consistency(contract_b: dict) -> dict:
    """Metrik 3 — dokumen yang bertentangan dengan dirinya sendiri.

    `steps` sebuah aktivitas dan `diagram_script`-nya harus menceritakan alur
    yang SAMA (prompt mewajibkannya). Yang dicari: aksi di diagram yang tak
    diceritakan SAMA SEKALI oleh teks — pembaca melihat sesuatu di gambar yang
    tak ada penjelasannya.

    Versi pertama metrik ini membandingkan JUMLAH langkah, dan langsung melahirkan
    false positive: satu aktivitas meringkas enam aksi jadi satu kalimat ("Admin
    memilih aksi: proses, tandai siap, ...") sementara diagramnya memecahnya jadi
    enam node. Ceritanya sama, kedalamannya beda — dan meringkas itu SAH. Itu
    kasus klasik "mengukur proksi, bukan barangnya": jumlah langkah bukan
    kesamaan cerita.
    """
    problems = []
    diagrams = contract_b.get("diagrams", {})
    for a in diagrams.get("activity_diagrams", []):
        steps = a.get("steps", [])
        actions = re.findall(r"^\s*:(.+);", a.get("diagram_script", ""), re.M)
        if not steps or not actions:
            continue
        orphan = [x.strip() for x in actions if not _covered(x, steps)]
        if orphan:
            problems.append(
                f"{a.get('activity_name')}: {len(orphan)} aksi diagram tak "
                f"diceritakan teks — mis. \"{orphan[0][:60]}\"")
    flow_steps = contract_b.get("business_flow_steps", [])
    flow_actions = re.findall(r"^\s*:(.+);", diagrams.get("business_process_flow", ""), re.M)
    if flow_steps and flow_actions:
        orphan = [x.strip() for x in flow_actions if not _covered(x, flow_steps)]
        if orphan:
            problems.append(
                f"business flow: {len(orphan)} aksi diagram tak diceritakan teks — "
                f"mis. \"{orphan[0][:60]}\"")
    return {"masalah": problems, "jumlah": len(problems)}


def evaluate(contract_a: dict, contract_b: dict) -> dict:
    return {
        "grounding": grounding(contract_a, contract_b),
        "representasi": representation(contract_a, contract_b),
        "konsistensi": consistency(contract_b),
    }


def _report(result: dict) -> int:
    g, r, c = result["grounding"], result["representasi"], result["konsistensi"]
    print("=" * 70)
    print("EVALUASI ISI DOKUMEN")
    print("=" * 70)
    print(f"\n1. GROUNDING (karangan)      {g['berjejak']}/{g['total_istilah']} "
          f"istilah berjejak = {g['rasio']:.0%}")
    for t in g["tak_berjejak"][:10]:
        print(f"     TAK BERJEJAK: {t}")
    print(f"\n2. REPRESENTASI (kelalaian)  {r['tersinggung']}/{r['total_endpoint']} "
          f"endpoint tersinggung = {r['rasio']:.0%}")
    for p in r["tak_tersinggung"][:10]:
        print(f"     TAK DICERITAKAN: {p}")
    print(f"\n3. KONSISTENSI               {c['jumlah']} pertentangan")
    for p in c["masalah"]:
        print(f"     {p}")
    print("\n" + "-" * 70)
    print("Catatan: grounding membuktikan 'tidak dikarang', BUKAN 'benar'.")
    print("Salah-sumber (mis. kode dari folder tutorial) LOLOS dari metrik ini —")
    print("akurasi semantik tetap butuh manusia yang membaca kode.")
    # Gagal hanya kalau ada karangan atau pertentangan; representasi rendah itu
    # SINYAL untuk diperiksa, bukan otomatis salah (repo bisa punya endpoint
    # internal yang memang tak layak masuk dokumen).
    return 1 if (g["tak_berjejak"] or c["jumlah"]) else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    a = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    b = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    sys.exit(_report(evaluate(a, b)))
