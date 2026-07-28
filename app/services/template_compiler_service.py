"""V2 — kompilasi template yang di-upload user jadi template TERDAFTAR.

Orkestrator yang menyatukan increment 1-3 jadi satu langkah:

    docx upload → ukur (TemplateSpec) → usulkan peta bab → generate template Jinja
                → sintesis reference.docx → simpan di data/templates/<id>/ → daftar.

Sesudah itu `compiler_service.generate_docx(..., template_id=<id baru>)` merender
dokumen bergaya template yang di-upload — MEMAKAI ULANG seluruh pipeline matang
(Contract B → Jinja → Pandoc → reference.docx). Inilah keputusan arsitektur V2:
"kompilasi upload jadi template terdaftar", bukan swap `--reference-doc` runtime
(yang V0 buktikan menghasilkan paket corrupt).

Persis kerja MANUAL pembuatan template `premco` (V1) — diotomatiskan. Default
DETERMINISTIK & $0: peta bab heuristik (`propose_mapping`). Peta bab BER-LLM
tersedia OPT-IN lewat `use_llm_mapping=True` (berbayar, `llm_mapping_service`) —
memetakan bab asing yang kata kuncinya tak cocok; kontrak peta
(`[{level,text,binding}]`) identik jadi keduanya dipertukarkan. UI tinjauan menyusul.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Modul (bukan `from ... import TEMPLATES_STORE`) supaya TEMPLATES_STORE punya
# SATU sumber kebenaran di compiler_service — penting agar redirect (test/config)
# cukup di satu tempat, bukan dua binding yang bisa menyimpang.
from app.services import compiler_service
from app.services.llm_mapping_service import llm_propose_mapping
from app.services.reference_synthesis_service import build_reference
from app.services.template_generator_service import (
    ALL_BINDINGS, CONTENT_BINDINGS, generate_jinja_template, mapping_health,
    propose_mapping)
from app.services.template_spec_service import build_template_spec

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("-", (name or "").lower()).strip("-")[:48]


def _unique_template_id(preferred: str) -> str:
    """template_id yang belum dipakai built-in maupun template terkompilasi lain —
    supaya tak menimpa `default`/`premco` atau upload sebelumnya."""
    taken = set(compiler_service.list_template_ids())
    candidate = preferred or f"tpl-{uuid.uuid4().hex[:8]}"
    if candidate not in taken:
        return candidate
    for i in range(2, 1000):
        if f"{candidate}-{i}" not in taken:
            return f"{candidate}-{i}"
    return f"{candidate}-{uuid.uuid4().hex[:8]}"


def _pick_doc_types(spec: dict, requested) -> list[str]:
    if requested:
        return [d.upper() for d in requested]
    guess = spec.get("doc_kind_guess", "unknown")
    return [guess] if guess in ("SDD", "UAT") else ["SDD"]


def compile_template(spec: dict, name: str, doc_types=None,
                     template_id: str | None = None,
                     use_llm_mapping: bool = False) -> dict:
    """`TemplateSpec` → template terdaftar. Menulis ke data/templates/<id>/:
    template Jinja per doc_type (`.md`), rencana peta (`mapping_<dt>.json`),
    reference.docx tersintesis, spec (`spec.json`), dan manifest (`template.json`).
    Mengembalikan manifest.

    doc_types: jenis dokumen yang dibuatkan template. None = tebak dari
    `spec.doc_kind_guess` (fallback ["SDD"]) — meng-generate template UAT dari
    outline SDD (atau sebaliknya) cuma menghasilkan placeholder, jadi tak berguna.

    use_llm_mapping: False (default) = peta bab heuristik ($0, deterministik).
    True = peta bab BER-LLM (`llm_mapping_service`, BERBAYAR — satu panggilan
    Claude per doc_type) yang memetakan bab asing yang kata kuncinya tak cocok.
    """
    doc_types = _pick_doc_types(spec, doc_types)
    template_id = _unique_template_id(template_id or _slugify(name))
    base = compiler_service.TEMPLATES_STORE / template_id
    base.mkdir(parents=True, exist_ok=True)

    doc_type_files = {}
    health = {}
    for dt in doc_types:
        mapping = (llm_propose_mapping(spec, dt) if use_llm_mapping
                   else propose_mapping(spec, dt))
        (base / f"mapping_{dt}.json").write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        (base / f"{dt}.md").write_text(
            generate_jinja_template(mapping), encoding="utf-8")
        doc_type_files[dt] = f"{dt}.md"
        health[dt] = mapping_health(mapping, dt)

    # Sintesis reference.docx dari spec (increment 2) — identitas visual template.
    build_reference(base / "reference.docx", spec=spec)
    (base / "spec.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "template_id": template_id,
        "name": name,
        "doc_types": doc_type_files,
        "reference": "reference.docx",
        # Flag perilaku yang tak terlihat dari nama template (dibaca _resolve_template).
        # Template hasil-generate: TAK memakai Component Integration (generator tak
        # meng-emit-nya — sama seperti premco, sekaligus menghindari crash diagram
        # dari nama file dynamic-route); UAT-nya memakai tabel test per-modul
        # (generator meng-emit `uat_test_groups`); tanpa --toc.
        "uses_component_integration": False,
        "groups_test_cases": True,
        "uat_toc": False,
        # Seberapa banyak template ini akan terisi otomatis — ikut manifest supaya
        # pemanggil API bisa memperingatkan pengguna SEBELUM dia membayar LLM
        # untuk dokumen yang ternyata mayoritas placeholder.
        "mapping_health": health,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (base / "template.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def compile_template_from_docx(docx_path, name: str | None = None, doc_types=None,
                               template_id: str | None = None,
                               use_llm_mapping: bool = False) -> dict:
    """Jalur lengkap dari file `.docx` yang di-upload: ukur (`build_template_spec`)
    → `compile_template`. `.doc` biner harus dikonversi ke `.docx` dulu.
    `use_llm_mapping` diteruskan ke `compile_template` (lihat di sana)."""
    spec = build_template_spec(docx_path)
    return compile_template(spec, name or Path(docx_path).stem, doc_types, template_id,
                            use_llm_mapping=use_llm_mapping)


def update_mapping(template_id: str, doc_type: str, bindings: list[str]) -> dict:
    """Ganti binding peta bab hasil TINJAUAN MANUSIA, lalu generate ulang template Jinja.

    Langkah terakhir yang tak bisa diotomatiskan. Ekstraksi bisa menemukan semua
    bab dan pemeta (heuristik maupun LLM) bisa menebak isinya, tapi tak satu pun
    tahu bahwa bab "Setup" di template vendor itu tempat SCREENSHOT — itu
    pengetahuan yang cuma dimiliki orang yang memberikan templatenya.

    `bindings` adalah daftar PARALEL dengan peta tersimpan: satu binding per bab,
    urutan sama. Sengaja bukan peta utuh — struktur bab (level/teks/orientasi)
    adalah hasil PENGUKURAN dokumen sumber, bukan pendapat; membiarkannya
    dikirim ulang cuma membuka jalan merusaknya tanpa menambah kemampuan apa pun.

    ValueError untuk seluruh penolakan (dipetakan ke 4xx oleh route).
    """
    base = compiler_service.TEMPLATES_STORE / template_id
    manifest_path = base / "template.json"
    if not manifest_path.exists():
        raise ValueError(f"Template terkompilasi tidak ditemukan: {template_id!r}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    doc_type = doc_type.upper()
    if doc_type not in manifest.get("doc_types", {}):
        raise ValueError(
            f"Template {template_id!r} tidak punya doc_type {doc_type!r} "
            f"(punya: {sorted(manifest.get('doc_types', {}))}).")

    plan = json.loads((base / f"mapping_{doc_type}.json").read_text(encoding="utf-8"))
    if len(bindings) != len(plan):
        raise ValueError(
            f"Jumlah binding ({len(bindings)}) tak cocok dengan jumlah bab "
            f"({len(plan)}). Peta harus dikirim utuh, satu binding per bab.")

    unknown = sorted({b for b in bindings if b not in ALL_BINDINGS})
    if unknown:
        raise ValueError(f"Binding tak dikenal: {unknown}. "
                         f"Yang tersedia: {sorted(ALL_BINDINGS)}.")

    # Isi turunan-kode cuma punya SATU sumber di Contract B, jadi memakainya di
    # dua bab menyalin paragraf/diagram yang sama dua kali. Pemeta otomatis
    # men-dedup diam-diam (yang pertama menang), tapi di sini suntingan itu
    # DISENGAJA — menelannya diam-diam berarti diam-diam mengabaikan perintah user.
    duplicated = sorted({b for b in bindings
                         if b in CONTENT_BINDINGS and bindings.count(b) > 1})
    if duplicated:
        raise ValueError(
            f"Isi yang sama dipakai lebih dari satu bab: {duplicated}. "
            f"Tiap isi turunan-kode cuma punya satu sumber, jadi bab kedua akan "
            f"menyalin isi bab pertama — pilih salah satu.")

    updated = [{**entry, "binding": binding}
               for entry, binding in zip(plan, bindings)]
    (base / f"mapping_{doc_type}.json").write_text(
        json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    (base / f"{doc_type}.md").write_text(
        generate_jinja_template(updated), encoding="utf-8")

    manifest.setdefault("mapping_health", {})[doc_type] = mapping_health(updated, doc_type)
    manifest["mapping_reviewed_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return load_compiled_detail(template_id)


def load_compiled_detail(template_id: str) -> dict:
    """Manifest + rencana peta bab per doc_type untuk template terkompilasi —
    dipakai respons upload & UI tinjauan pemetaan. `mappings` = `{DOC:
    [{level,text,binding}]}`, isian yang kelak diedit manusia sebelum generate.
    ValueError kalau `template_id` bukan template hasil-kompilasi (mis. built-in)."""
    base = compiler_service.TEMPLATES_STORE / template_id
    manifest_path = base / "template.json"
    if not manifest_path.exists():
        raise ValueError(f"Template terkompilasi tidak ditemukan: {template_id!r}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mappings = {}
    for dt in manifest.get("doc_types", {}):
        mapping_path = base / f"mapping_{dt}.json"
        if mapping_path.exists():
            mappings[dt] = json.loads(mapping_path.read_text(encoding="utf-8"))
    # Template yang dikompilasi SEBELUM `mapping_health` ada tetap harus menjawab
    # pertanyaan "template ini akan terisi berapa?" — dihitung ulang dari peta
    # yang tersimpan, jadi UI tak perlu tahu template ini lama atau baru.
    if "mapping_health" not in manifest:
        manifest["mapping_health"] = {dt: mapping_health(plan, dt)
                                      for dt, plan in mappings.items()}
    return {"manifest": manifest, "mappings": mappings}
