"""Ekspor & hapus data satu pengguna (#16).

Dua operasi yang dituntut regulasi privasi (GDPR "right of access" & "right to
erasure", UU PDP Pasal 8 & 9), dan satu prinsip yang mengikat keduanya: **daftar
tempat penyimpanan cuma boleh ada di SATU berkas.** Kalau tiap penambahan tabel
harus diingat manual di dua tempat, cepat atau lambat ada yang tertinggal — dan
tertinggalnya baru ketahuan saat seseorang menanyakan datanya yang katanya sudah
dihapus.

Lima tempat data pengguna hidup, dan semuanya sudah ber-`owner` sejak #9/#10/#11:

| Tempat                       | Ekspor | Hapus                    |
|------------------------------|--------|--------------------------|
| tabel `jobs`                 | ✅     | dihapus                  |
| docx di `data/documents/`    | ✅     | dihapus                  |
| bundel `.drawio` pasangannya | ✅     | dihapus                  |
| `data/templates/<id>/`       | ✅     | dihapus                  |
| `user_subscriptions`         | ✅     | dihapus                  |
| `usage_records`              | ✅     | owner-nya DIANONIMKAN    |

Baris terakhir adalah satu-satunya yang tidak dihapus, dan itu keputusan sadar
pemilik project — alasannya ditulis di `billing_service.anonymize_usage_of`,
bukan diringkas di sini, supaya penjelasannya tinggal di sebelah kodenya.

**Kode sumber pengguna tidak muncul di tabel mana pun, dan itu memang jawabannya
untuk pertanyaan "kode saya ke mana".** Repo/ZIP dibaca ke memori, di-parse jadi
Contract A, dikirim ke API Anthropic untuk menghasilkan Contract B, lalu dibuang
saat job selesai. Yang bertahan di disk cuma dokumen jadinya.
"""
from __future__ import annotations

import json
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

from app.services import (billing_service, compiler_service, job_store,
                          template_compiler_service)
from app.services.auth_service import Principal

logger = logging.getLogger(__name__)


class AnonymousAccountError(Exception):
    """Operasi butuh identitas, tapi auth tidak aktif.

    Dipetakan ke HTTP 409 di boundary — bukan 401 (tak ada yang gagal login) dan
    bukan 403 (tak ada aturan yang dilanggar). Ini permintaan yang tak punya arti
    dalam konfigurasi saat ini.
    """


def _require_identifiable(principal: Principal) -> str:
    """Owner yang benar-benar menunjuk satu orang, atau tolak.

    Penjaga TERPENTING di berkas ini. Saat `SUPABASE_URL` kosong, SETIAP
    pemanggil adalah `Principal(id="anonymous")` — jadi "hapus data saya" akan
    menghapus data semua orang di instance itu, dan permintaan yang paling
    mungkin memicunya justru datang dari orang yang cuma ingin membersihkan
    miliknya sendiri. Operasi yang tak bisa dibatalkan tidak boleh berjalan di
    atas identitas yang tidak membedakan siapa pun.
    """
    if principal.is_anonymous or not principal.id or principal.id == "anonymous":
        raise AnonymousAccountError(
            "Ekspor & hapus data butuh akun. Instance ini berjalan tanpa "
            "autentikasi (SUPABASE_URL kosong), jadi semua data di sini milik "
            "satu identitas anonim yang sama dan tidak bisa dipisahkan per orang."
        )
    return principal.id


def collect_user_data(owner: str) -> dict:
    """Seluruh data `owner` dalam bentuk dict — inti ekspor, dan sekaligus yang
    diperiksa test hapus untuk membuktikan tak ada sisa."""
    return {
        "owner": owner,
        "jobs": job_store.list_jobs(owner, limit=100_000),
        "subscription": billing_service.get_subscription_row(owner),
        "usage_records": billing_service.usage_records_of(owner),
        "templates": [
            json.loads((d / "template.json").read_text(encoding="utf-8"))
            for d in template_compiler_service.template_dirs_of_owner(owner)
        ],
    }


def export_user_data(principal: Principal) -> Path:
    """ZIP berisi seluruh data `principal`. Kembalikan path-nya (di direktori temp).

    Isinya dibuat supaya berguna untuk MANUSIA, bukan cuma untuk memenuhi
    kewajiban: `data.json` untuk yang terstruktur, plus dokumen `.docx` asli dan
    bundel diagramnya sehingga pengguna benar-benar membawa pulang hasil
    kerjanya — bukan sekadar daftar bahwa hasil itu pernah ada.
    """
    owner = _require_identifiable(principal)
    data = collect_user_data(owner)

    tmp_dir = Path(tempfile.mkdtemp(prefix="export-"))
    zip_path = tmp_dir / "data-saya.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data.json",
                    json.dumps(data, ensure_ascii=False, indent=2, default=str))
        zf.writestr("BACA-SAYA.txt", _readme_text(data))

        for job in data["jobs"]:
            docx_path = job.get("docx_path")
            if not docx_path:
                continue
            source = Path(docx_path)
            if source.exists():
                zf.write(source, f"dokumen/{job['id']}_{source.name}")
            bundle = compiler_service.drawio_bundle_for(docx_path)
            if bundle.exists():
                zf.write(bundle, f"dokumen/{job['id']}_{bundle.name}")

        for template_dir in template_compiler_service.template_dirs_of_owner(owner):
            for path in sorted(template_dir.rglob("*")):
                if path.is_file():
                    rel = path.relative_to(template_dir.parent)
                    zf.write(path, f"template/{rel.as_posix()}")

    return zip_path


def _readme_text(data: dict) -> str:
    """Penjelasan isi ZIP. Ada karena arsip data tanpa keterangan memenuhi
    kewajiban hukum tapi gagal pada tujuannya: pengguna harus MENGERTI apa yang
    disimpan tentang dirinya, bukan cuma menerimanya."""
    return (
        "ISI ARSIP INI\n"
        "=============\n\n"
        f"Akun            : {data['owner']}\n"
        f"Jumlah dokumen  : {len(data['jobs'])}\n"
        f"Jumlah template : {len(data['templates'])}\n\n"
        "data.json     - seluruh data terstruktur: riwayat job, langganan,\n"
        "                catatan pemakaian token, dan manifest template.\n"
        "dokumen/      - berkas .docx hasil generate yang masih tersimpan,\n"
        "                berikut bundel diagram .drawio bila ada. Dokumen yang\n"
        "                sudah lewat masa simpan (30 hari) tidak ada di sini;\n"
        "                riwayatnya tetap tercatat di data.json.\n"
        "template/     - template dokumen yang Anda unggah, sesudah dikompilasi.\n\n"
        "TIDAK ADA DI SINI, dan memang tidak pernah disimpan: kode sumber yang\n"
        "Anda analisis. Kode dibaca ke memori, diproses, lalu dibuang saat job\n"
        "selesai. Yang bertahan di server cuma dokumen hasilnya.\n"
    )


def delete_user_data(principal: Principal) -> dict:
    """Hapus seluruh data `principal`. Kembalikan ringkasan apa yang dihapus.

    Ringkasannya bukan hiasan: permintaan hapus yang dijawab "ok" saja tak bisa
    dibedakan dari permintaan hapus yang diam-diam tak menemukan apa pun karena
    salah owner. Angka membuat kegagalan itu terlihat.

    Urutannya sengaja: job & template (yang paling banyak, dan yang memegang
    berkas di disk) lebih dulu, catatan billing terakhir. Kalau prosesnya mati di
    tengah, yang tertinggal adalah baris billing tanpa job — bukan sebaliknya,
    yang berarti dokumen pengguna masih ada di disk sementara catatannya hilang
    dan tak ada lagi yang tahu berkas itu harus dihapus.
    """
    owner = _require_identifiable(principal)

    jobs_summary = job_store.delete_jobs_of_owner(owner)
    templates_removed = template_compiler_service.delete_templates_of_owner(owner)
    subscriptions_removed = billing_service.delete_subscription_of(owner)
    usage_anonymized = billing_service.anonymize_usage_of(owner)

    summary = {
        "owner": owner,
        "jobs_deleted": jobs_summary["jobs"],
        "documents_deleted": jobs_summary["documents"],
        "templates_deleted": templates_removed,
        "subscriptions_deleted": subscriptions_removed,
        "usage_records_anonymized": usage_anonymized,
    }
    logger.info("Data pengguna dihapus atas permintaan: %s", summary)
    return summary


def residual_data(owner: str) -> Optional[dict]:
    """Sisa data `owner` sesudah penghapusan — None kalau benar-benar bersih.

    Dipakai test untuk memeriksa BARANGNYA, bukan nilai kembalian
    `delete_user_data`. Bedanya menentukan: ringkasan itu laporan fungsi tentang
    dirinya sendiri, dan laporan itu tetap terlihat benar walau ada tabel yang
    lupa disapu. Ini menanyakan ulang ke penyimpanannya.
    """
    data = collect_user_data(owner)
    sisa = {k: v for k, v in data.items() if k != "owner" and v}
    return sisa or None
