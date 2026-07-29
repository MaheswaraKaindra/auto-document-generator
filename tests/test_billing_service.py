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
    """Checkout session dalam mode stub ketika STRIPE_SECRET_KEY tidak disetel."""
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", None)
    res = billing_service.create_stripe_checkout_session("usr_stub_1", "test@stub.com")
    assert res["is_stub"] is True
    assert "billing=success_stub" in res["checkout_url"]


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
