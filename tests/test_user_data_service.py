"""Ekspor & hapus data pengguna (#16).

Prinsip yang mengatur file ini: **periksa barangnya, bukan laporan fungsinya.**
`delete_user_data` mengembalikan ringkasan tentang dirinya sendiri, dan ringkasan
itu akan tetap terlihat benar seandainya ada satu tabel yang lupa disapu — persis
kelas kegagalan yang paling mahal di sini, sebab gejalanya bukan error melainkan
data yang katanya sudah hilang tapi masih ada. Karena itu tiap test hapus
mengakhiri dengan menanyakan ULANG ke penyimpanannya (`residual_data`).
"""

import json
import zipfile
from pathlib import Path

import pytest

from app.services import (billing_service, compiler_service, job_store,
                          template_compiler_service, user_data_service)
from app.services.auth_service import ANONYMOUS, Principal

ALICE = Principal(id="user-alice", email="alice@contoh.com", is_anonymous=False)
BOB = Principal(id="user-bob", email="bob@contoh.com", is_anonymous=False)


@pytest.fixture(autouse=True)
def _tmp_store(tmp_path, monkeypatch):
    """DB & direktori berkas sementara — hermetik, dan (penting untuk file ini)
    memastikan test hapus tak pernah menyentuh data mesin pengembang."""
    db_file = tmp_path / "jobs.db"
    monkeypatch.setattr(job_store, "DB_PATH", db_file)
    monkeypatch.setattr(billing_service, "DB_PATH", db_file)
    monkeypatch.setattr(compiler_service, "TEMPLATES_STORE", tmp_path / "templates")
    job_store.init_db()
    billing_service.init_billing_db()
    return tmp_path


def _job_dengan_dokumen(owner, tmp_path, nama="dok.docx", dengan_drawio=False):
    """Job berstatus done + docx sungguhan di disk (+ bundel .drawio opsional).

    Mengembalikan path TERSIMPAN, bukan path sumber: `mark_done` menyalin docx ke
    `data/documents/<job_id>.docx` dan mencatat salinan itulah yang di DB. Salinan
    itu yang harus ikut terhapus — memeriksa file sumber akan lolos tanpa
    membuktikan apa pun."""
    job_id = job_store.create_job("SDD", "Proyek Uji", owner=owner)
    sumber = tmp_path / f"sumber_{job_id}_{nama}"
    sumber.write_bytes(b"PK\x03\x04 docx palsu")
    if dengan_drawio:
        compiler_service.drawio_bundle_for(sumber).write_bytes(b"PK\x03\x04 drawio")
    job_store.mark_done(job_id, str(sumber))
    return job_id, Path(job_store.get_job(job_id)["docx_path"])


def _template(owner, template_id="tpl-uji"):
    """Template terkompilasi milik `owner` di store sementara."""
    base = compiler_service.TEMPLATES_STORE / template_id
    base.mkdir(parents=True)
    (base / "template.json").write_text(
        json.dumps({"id": template_id, "owner": owner, "name": "Template Uji",
                    "doc_types": {"SDD": "sdd.md"}}),
        encoding="utf-8")
    (base / "sdd.md").write_text("# {{ meta.judul }}", encoding="utf-8")
    return base


# --- Penjaga mode dev --------------------------------------------------------

def test_hapus_ditolak_saat_auth_mati():
    """Penjaga TERPENTING di fitur ini.

    Tanpa auth, setiap pemanggil adalah `Principal(id="anonymous")` yang SAMA —
    jadi "hapus data saya" akan mengosongkan data semua orang di instance itu.
    Operasi yang tak bisa dibatalkan tidak boleh jalan di atas identitas yang tak
    membedakan siapa pun."""
    with pytest.raises(user_data_service.AnonymousAccountError):
        user_data_service.delete_user_data(ANONYMOUS)


def test_ekspor_juga_ditolak_saat_auth_mati():
    with pytest.raises(user_data_service.AnonymousAccountError):
        user_data_service.export_user_data(ANONYMOUS)


def test_penjaga_tak_bisa_dilewati_dengan_id_anonymous():
    """`is_anonymous=False` tapi id-nya tetap "anonymous" — bentuk yang bisa
    lahir dari provider auth lain kelak. Yang diperiksa harus id-nya juga,
    bukan cuma flag-nya."""
    palsu = Principal(id="anonymous", email=None, is_anonymous=False)
    with pytest.raises(user_data_service.AnonymousAccountError):
        user_data_service.delete_user_data(palsu)


# --- Hapus -------------------------------------------------------------------

def test_hapus_menyapu_kelima_tempat_penyimpanan(_tmp_store):
    """Satu test yang menyentuh KELIMA tempat sekaligus, bukan lima test kecil:
    yang diuji di sini bukan tiap penyapu (masing-masing sudah punya testnya),
    melainkan bahwa daftarnya LENGKAP. Tempat yang lupa didaftarkan hanya
    kelihatan dari test yang mengisi semuanya lalu memeriksa tak ada sisa."""
    job_id, docx = _job_dengan_dokumen(ALICE.id, _tmp_store, dengan_drawio=True)
    bundle = compiler_service.drawio_bundle_for(docx)
    template_dir = _template(ALICE.id)
    billing_service.set_user_tier(owner=ALICE.id, tier=billing_service.TIER_PRO)
    billing_service.record_job_usage(
        ALICE.id, job_id, "SDD",
        {"input_tokens": 1_000, "output_tokens": 500})

    summary = user_data_service.delete_user_data(ALICE)

    assert summary["jobs_deleted"] == 1
    assert summary["documents_deleted"] == 1
    assert summary["templates_deleted"] == 1
    assert summary["subscriptions_deleted"] == 1
    assert summary["usage_records_anonymized"] == 1

    # Barangnya, bukan laporannya:
    assert not docx.exists(), "docx masih ada di disk"
    assert not bundle.exists(), "bundel .drawio masih ada di disk"
    assert not template_dir.exists(), "direktori template masih ada"
    assert job_store.get_job(job_id) is None
    assert user_data_service.residual_data(ALICE.id) is None


def test_hapus_tak_menyentuh_data_pengguna_lain(_tmp_store):
    """Kegagalan yang paling merusak di fitur ini bukan "gagal menghapus",
    melainkan "menghapus milik orang lain" — dan itu tak bisa dibatalkan."""
    _, docx_alice = _job_dengan_dokumen(ALICE.id, _tmp_store, "alice.docx")
    job_bob, docx_bob = _job_dengan_dokumen(BOB.id, _tmp_store, "bob.docx")
    _template(ALICE.id, "tpl-alice")
    tpl_bob = _template(BOB.id, "tpl-bob")
    billing_service.set_user_tier(owner=BOB.id, tier=billing_service.TIER_PRO)

    user_data_service.delete_user_data(ALICE)

    assert not docx_alice.exists()
    assert docx_bob.exists(), "dokumen pengguna lain ikut terhapus"
    assert tpl_bob.exists(), "template pengguna lain ikut terhapus"
    assert job_store.get_job(job_bob) is not None
    assert billing_service.get_user_tier(BOB.id) == billing_service.TIER_PRO
    assert user_data_service.residual_data(BOB.id) is not None


def test_template_tanpa_owner_tidak_ikut_terhapus(_tmp_store):
    """Manifest tanpa `owner` (dikompilasi sebelum kolom itu ada, atau dari mode
    dev) diperlakukan `visible_to` sebagai MILIK BERSAMA. Menghapusnya atas nama
    satu pengguna berarti mengambil template milik semua orang."""
    base = compiler_service.TEMPLATES_STORE / "tpl-warisan"
    base.mkdir(parents=True)
    (base / "template.json").write_text(json.dumps({"id": "tpl-warisan"}),
                                        encoding="utf-8")

    user_data_service.delete_user_data(ALICE)

    assert base.exists(), "template milik bersama ikut terhapus"


def test_usage_record_dianonimkan_bukan_dihapus(_tmp_store):
    """Keputusan pemilik project: baris ini catatan biaya, jadi angkanya bertahan
    sementara tautannya ke orang diputus."""
    job_id, _ = _job_dengan_dokumen(ALICE.id, _tmp_store)
    billing_service.record_job_usage(
        ALICE.id, job_id, "SDD",
        {"input_tokens": 1_000, "output_tokens": 500})

    user_data_service.delete_user_data(ALICE)

    assert billing_service.usage_records_of(ALICE.id) == []
    tersisa = billing_service.usage_records_of(billing_service.ANONYMIZED_OWNER)
    assert len(tersisa) == 1
    assert tersisa[0]["input_tokens"] == 1_000
    # Tak boleh ada jejak balik ke orangnya di baris yang tersisa.
    assert ALICE.id not in json.dumps(tersisa, default=str)


def test_hapus_pada_akun_kosong_jujur_melaporkan_nol():
    """"0 dihapus" harus terlihat, bukan disamarkan jadi sukses tanpa angka —
    itu satu-satunya cara membedakan "tak punya data" dari "salah owner"."""
    summary = user_data_service.delete_user_data(ALICE)

    assert summary["jobs_deleted"] == 0
    assert summary["templates_deleted"] == 0
    assert summary["usage_records_anonymized"] == 0


def test_penyapu_menolak_owner_kosong():
    """Pertahanan berlapis: penjaga anonim ada di service, tapi penyapunya bisa
    dipanggil dari tempat lain kelak (CLI, migrasi). `owner` kosong akan menyapu
    baris ber-owner NULL — yaitu SELURUH data mode dev."""
    with pytest.raises(ValueError):
        job_store.delete_jobs_of_owner("")
    with pytest.raises(ValueError):
        billing_service.anonymize_usage_of("")
    with pytest.raises(ValueError):
        template_compiler_service.delete_templates_of_owner("")


# --- Ekspor ------------------------------------------------------------------

def test_ekspor_berisi_data_dokumen_dan_template(_tmp_store):
    job_id, _ = _job_dengan_dokumen(ALICE.id, _tmp_store, dengan_drawio=True)
    _template(ALICE.id)
    billing_service.record_job_usage(
        ALICE.id, job_id, "SDD",
        {"input_tokens": 1_000, "output_tokens": 500})

    zip_path = user_data_service.export_user_data(ALICE)

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        data = json.loads(zf.read("data.json"))

    assert "BACA-SAYA.txt" in names
    assert any(n.startswith("dokumen/") and n.endswith(".docx") for n in names)
    assert any(n.endswith("_diagrams.zip") for n in names), \
        "bundel diagram tak ikut terekspor"
    assert any(n.startswith("template/") for n in names)

    assert data["owner"] == ALICE.id
    assert len(data["jobs"]) == 1
    assert len(data["usage_records"]) == 1
    assert len(data["templates"]) == 1


def test_ekspor_tak_membocorkan_data_pengguna_lain(_tmp_store):
    _job_dengan_dokumen(BOB.id, _tmp_store, "rahasia-bob.docx")
    _template(BOB.id, "tpl-bob")
    _job_dengan_dokumen(ALICE.id, _tmp_store, "punya-alice.docx")

    zip_path = user_data_service.export_user_data(ALICE)

    with zipfile.ZipFile(zip_path) as zf:
        gabungan = " ".join(zf.namelist()) + zf.read("data.json").decode()

    # Nama berkas tersimpan adalah `<job_id>.docx`, jadi yang menjadi bukti di
    # sini bukan nama filenya melainkan id pemilik & id template — dua hal yang
    # memang akan ikut kalau penyaringan owner bocor.
    assert BOB.id not in gabungan
    assert "tpl-bob" not in gabungan


def test_ekspor_dokumen_kedaluwarsa_tetap_menyebut_riwayatnya(_tmp_store):
    """Dokumen yang sudah lewat masa simpan 30 hari tak punya file lagi, tapi
    barisnya tetap ada. Ekspor tak boleh meledak karenanya — dan harus tetap
    menyerahkan riwayatnya, sebab itu pun data tentang orang tersebut."""
    job_id, docx = _job_dengan_dokumen(ALICE.id, _tmp_store)
    docx.unlink()   # persis yang dilakukan purge_expired_documents: file tersimpan
                    # hilang, barisnya tinggal

    zip_path = user_data_service.export_user_data(ALICE)

    with zipfile.ZipFile(zip_path) as zf:
        data = json.loads(zf.read("data.json"))
        assert not any(n.endswith(".docx") for n in zf.namelist())

    assert [j["id"] for j in data["jobs"]] == [job_id]
