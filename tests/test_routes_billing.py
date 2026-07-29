"""Test endpoint HTTP billing & kuota (/billing/*)."""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.main import app
from app.services import billing_service, job_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_tmp_db(tmp_path, monkeypatch):
    """Gunakan database SQLite sementara."""
    db_file = tmp_path / "jobs.db"
    monkeypatch.setattr(job_store, "DB_PATH", db_file)
    monkeypatch.setattr(billing_service, "DB_PATH", db_file)
    job_store.init_db()
    billing_service.init_billing_db()


def test_get_billing_usage_endpoint():
    """GET /billing/usage mengembalikan status kuota dan pemakaian."""
    res = client.get("/billing/usage")
    assert res.status_code == 200
    data = res.json()
    assert "tier" in data
    assert "limit" in data
    assert "jobs_used" in data
    assert "remaining" in data
    assert "total_tokens" in data


def test_post_billing_checkout_endpoint():
    """POST /billing/checkout mengembalikan URL checkout."""
    res = client.post("/billing/checkout")
    assert res.status_code == 200
    data = res.json()
    assert "checkout_url" in data


def test_generate_document_rejects_when_quota_exceeded(monkeypatch):
    """POST /documents/generate menolak dengan HTTP 402 saat kuota tier habis."""
    # Aktifkan auth dan set kuota 1
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config, "TIER_FREE_LIMIT", 1)

    mock_principal = billing_service.Principal(id="usr_quota_api", email="usr@test.com", is_anonymous=False)

    with patch("app.api.deps.get_current_user", return_value=mock_principal), \
         patch("app.services.rate_limit_service.check_generate") as mock_rl:
        mock_rl.return_value = billing_service.auth_service.Principal
        # Isi 1 job di DB agar kuota 1/1 habis
        job_store.create_job("SDD", "Proj Existing", owner="usr_quota_api")

        payload = {
            "document_type": "SDD",
            "project_name": "Test Project",
            "repositories": [{"repo_tag": "test", "repo_url": "https://github.com/foo/bar"}],
        }

        res = client.post("/documents/generate", json=payload)
        assert res.status_code == 402
        body = res.json()
        assert "detail" in body
        detail = body["detail"]
        assert detail["upgrade_required"] is True
        assert detail["used"] == 1
