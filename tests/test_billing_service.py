"""Test billing_service — metering token, hitungan biaya, kuota tier, & Stripe webhook."""

from unittest.mock import patch, MagicMock
import pytest
from app.core import config
from app.services import auth_service, billing_service, job_store
from app.services.auth_service import Principal


@pytest.fixture(autouse=True)
def setup_tmp_db(tmp_path, monkeypatch):
    """Gunakan database SQLite sementara untuk setiap test agar hermetik."""
    db_file = tmp_path / "jobs.db"
    monkeypatch.setattr(job_store, "DB_PATH", db_file)
    monkeypatch.setattr(billing_service, "DB_PATH", db_file)
    job_store.init_db()
    billing_service.init_billing_db()


def test_calculate_llm_cost_usd():
    """Perhitungan harga Anthropic Claude Sonnet 5."""
    # 1,000,000 input = $3.00, 1,000,000 output = $15.00
    cost = billing_service.calculate_llm_cost_usd(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_read_tokens=0,
        cache_write_tokens=0,
    )
    assert cost == 18.0

    # Test dengan token kecil
    cost_small = billing_service.calculate_llm_cost_usd(
        input_tokens=10_000,   # 0.03
        output_tokens=2_000,   # 0.03
        cache_read_tokens=50_000, # 0.015
        cache_write_tokens=10_000, # 0.0375
    )
    assert cost_small > 0.0


def test_record_job_usage_and_summary():
    """Mencatat pemakaian job dan menghitung ringkasan pemakaian."""
    owner = "user_test_123"
    job_id = "job_abc_1"

    usage_dict = {
        "input_tokens": 50_000,
        "output_tokens": 5_000,
        "cache_read_input_tokens": 10_000,
        "cache_creation_input_tokens": 0,
    }

    rec = billing_service.record_job_usage(owner, job_id, "SDD", usage_dict)
    assert rec["owner"] == owner
    assert rec["job_id"] == job_id
    assert rec["estimated_cost_usd"] > 0

    # Buat dummy job di `jobs` table
    job_store.create_job("SDD", "Project Test", owner=owner)

    summary = billing_service.get_user_usage_summary(owner)
    assert summary["owner"] == owner
    assert summary["tier"] == "free"
    assert summary["jobs_used"] == 1
    assert summary["total_tokens"] == 65_000
    assert summary["total_cost_usd"] > 0.0


def test_quota_enforcement(monkeypatch):
    """Verifikasi penegakan kuota paket Free vs Pro."""
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    user_principal = Principal(id="usr_quota_test", email="user@test.com", is_anonymous=False)

    # Dev/anonymous mode -> tidak dibatasi
    anon_caller = auth_service.ANONYMOUS
    allowed, limit, used, reason = billing_service.check_quota_available(anon_caller)
    assert allowed is True

    # User Free tier default limit 3
    monkeypatch.setattr(config, "TIER_FREE_LIMIT", 3)
    allowed, limit, used, reason = billing_service.check_quota_available(user_principal)
    assert allowed is True
    assert limit == 3
    assert used == 0

    # Buat 3 job
    for _ in range(3):
        job_store.create_job("SDD", "Proj", owner=user_principal.id)

    # Job ke-4 -> kuota habis
    allowed, limit, used, reason = billing_service.check_quota_available(user_principal)
    assert allowed is False
    assert used == 3
    assert "Kuota tier FREE Anda habis" in reason

    # Upgrade ke Pro -> kuota terbuka kembali
    billing_service.set_user_tier(user_principal.id, "pro")
    allowed, limit, used, reason = billing_service.check_quota_available(user_principal)
    assert allowed is True
    assert billing_service.get_user_tier(user_principal.id) == "pro"


def test_stripe_checkout_stub(monkeypatch):
    """Tanpa STRIPE_SECRET_KEY: checkout jalan mode simulasi, dan tier TIDAK naik.

    Yang dijaga bukan cuma bentuk balasannya — tapi bahwa "checkout" tanpa Stripe
    tak menyentuh langganan sama sekali. Satu-satunya yang boleh menaikkan tier
    adalah webhook ber-signature sah.
    """
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", None)
    res = billing_service.create_stripe_checkout_session("usr_stub_1", "test@stub.com")
    assert res["is_stub"] is True
    assert "billing=simulasi" in res["checkout_url"]
    assert billing_service.get_user_tier("usr_stub_1") == "free"


def test_checkout_menolak_berisik_saat_price_id_kosong(monkeypatch):
    """Stripe aktif tapi STRIPE_PRO_PRICE_ID kosong = salah konfigurasi, dan harus
    berteriak menyebut env-nya — bukan jatuh sebagai error parameter dari Stripe."""
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_mock")
    monkeypatch.setattr(config, "STRIPE_PRO_PRICE_ID", None)
    with pytest.raises(ValueError, match="STRIPE_PRO_PRICE_ID"):
        billing_service.create_stripe_checkout_session("usr_x", "x@test.com")


def test_job_gagal_sebelum_llm_tak_memotong_kuota(monkeypatch):
    """Kuota mengukur pemakaian yang BENAR-BENAR terjadi, bukan berapa kali tombol
    ditekan. Job yang mati sebelum LLM (URL repo salah, ZIP rusak) nol biaya."""
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config, "TIER_FREE_LIMIT", 3)
    caller = Principal(id="usr_gagal", email="g@test.com", is_anonymous=False)

    # Dua job mati di ingest — nol panggilan LLM, jadi nol baris usage_records.
    for _ in range(2):
        jid = job_store.create_job("SDD", "Repo Salah", owner=caller.id)
        job_store.mark_failed(jid, "Repo tidak ditemukan", 422)

    allowed, limit, used, _ = billing_service.check_quota_available(caller)
    assert allowed is True
    assert used == 0, "job gagal sebelum LLM tak boleh memotong kuota"

    # Job yang gagal SESUDAH LLM dibayar (mis. render diagram tumbang) tetap
    # memotong: uangnya sudah keluar, dan itu yang diukur kuota.
    jid = job_store.create_job("SDD", "Diagram Tumbang", owner=caller.id)
    billing_service.record_job_usage(caller.id, jid, "SDD", {"input_tokens": 1000})
    job_store.mark_failed(jid, "PlantUML gagal", 500)

    allowed, limit, used, _ = billing_service.check_quota_available(caller)
    assert used == 1

    # Job yang masih jalan ikut dihitung — kalau tidak, request berbarengan bisa
    # menembus batas bersama-sama.
    job_store.create_job("SDD", "Sedang Jalan", owner=caller.id)
    _, _, used, _ = billing_service.check_quota_available(caller)
    assert used == 2


def test_tarif_mengikuti_model_yang_dipakai(monkeypatch):
    """Estimasi biaya memakai tarif `LLM_MODEL`, bukan tarif tetap Sonnet."""
    sonnet = billing_service.calculate_llm_cost_usd(
        1_000_000, 1_000_000, model="claude-sonnet-5")
    opus = billing_service.calculate_llm_cost_usd(
        1_000_000, 1_000_000, model="claude-opus-4-8")
    haiku = billing_service.calculate_llm_cost_usd(
        1_000_000, 1_000_000, model="claude-haiku-4-5")
    assert sonnet == 18.0          # $3 + $15
    assert opus == 30.0            # $5 + $25
    assert haiku == 6.0            # $1 + $5

    # Id ber-tanggal dicocokkan dari depan.
    assert billing_service.calculate_llm_cost_usd(
        1_000_000, 0, model="claude-haiku-4-5-20251001") == 1.0

    # Model tak dikenal: jatuh ke tarif default, TIDAK meledak — metering itu
    # pengamat, bukan penjaga gerbang.
    assert billing_service.calculate_llm_cost_usd(
        1_000_000, 0, model="model-masa-depan-9") == 3.0

    # Tanpa argumen `model`, tarifnya diambil dari config (yang dibaca aplikasi).
    monkeypatch.setattr(config, "LLM_MODEL", "claude-opus-4-8")
    assert billing_service.calculate_llm_cost_usd(1_000_000, 0) == 5.0


def test_limit_nol_tak_membatasi(monkeypatch):
    """`TIER_FREE_LIMIT = 0` (nilai DEFAULT-nya) berarti tanpa batas: memasang
    Supabase tidak boleh diam-diam menyalakan tembok berbayar.

    Diuji lewat perilaku, bukan dengan membaca `config.TIER_FREE_LIMIT` apa adanya
    — nilai itu datang dari `.env` mesin yang menjalankan tes, jadi menegaskannya
    di sini akan membuat tes gagal di mesin yang kebetulan mengisinya.
    """
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config, "TIER_FREE_LIMIT", 0)
    caller = Principal(id="usr_default", email="d@test.com", is_anonymous=False)
    for _ in range(5):
        job_store.create_job("SDD", "Proj", owner=caller.id)

    allowed, limit, used, _ = billing_service.check_quota_available(caller)
    assert allowed is True
    assert limit == 0
    assert used == 5


def test_stripe_webhook_handling(monkeypatch):
    """Handling Stripe webhook event checkout.session.completed."""
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_mock")
    monkeypatch.setattr(config, "STRIPE_WEBHOOK_SECRET", "whsec_mock")

    mock_event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": "usr_webhook_123",
                "customer": "cus_123",
                "subscription": "sub_456",
            }
        },
    }

    with patch("stripe.Webhook.construct_event", return_value=mock_event):
        success, msg = billing_service.handle_stripe_webhook(b"raw_body", "sig_header")
        assert success is True
        assert "diproses" in msg
        assert billing_service.get_user_tier("usr_webhook_123") == "pro"
