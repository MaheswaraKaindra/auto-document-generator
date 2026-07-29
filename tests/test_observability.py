"""Tes observability (#14): probe /ready, structured logging, seam Sentry.

Tak satu pun menyentuh layanan luar: Sentry di-uji lewat jalur MATI-nya (DSN
kosong = no-op) dan cek readiness di-mock di boundary fungsi cek — pola yang sama
dengan LLM/plantuml/Redis. Yang dijaga di sini adalah KEPUTUSANNYA (kapan ready
503, apa yang masuk ke baris JSON, kapan capture no-op), bukan bahwa Sentry/Java
bisa dihubungi.
"""

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.core import logging_config
from app.main import app
from app.services import readiness_service, telemetry

client = TestClient(app)


# --- Readiness probe ---------------------------------------------------------

def _ok(name):
    return lambda: {"name": name, "ok": True, "detail": "ok"}


def _bad(name):
    return lambda: {"name": name, "ok": False, "detail": "hilang"}


def test_readiness_ready_saat_semua_dependency_ada(monkeypatch):
    monkeypatch.setattr(readiness_service, "_CHECKS", (_ok("database"), _ok("pandoc")))
    result = readiness_service.readiness()
    assert result["ready"] is True
    assert all(c["ok"] for c in result["checks"])


def test_readiness_gagal_kalau_satu_dependency_hilang(monkeypatch):
    """Satu dependency hilang = pipeline pasti gagal, jadi TIDAK ada 'setengah siap'."""
    monkeypatch.setattr(readiness_service, "_CHECKS", (_ok("database"), _bad("java")))
    result = readiness_service.readiness()
    assert result["ready"] is False
    assert [c["name"] for c in result["checks"] if not c["ok"]] == ["java"]


def test_endpoint_ready_200_saat_siap(monkeypatch):
    monkeypatch.setattr(readiness_service, "readiness",
                        lambda: {"ready": True, "checks": []})
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["ready"] is True


def test_endpoint_ready_503_saat_tak_siap(monkeypatch):
    """Orchestrator butuh KODE, bukan cuma body: 503 = jangan kirim trafik ke sini."""
    monkeypatch.setattr(
        readiness_service, "readiness",
        lambda: {"ready": False, "checks": [{"name": "pandoc", "ok": False, "detail": "x"}]},
    )
    resp = client.get("/ready")
    assert resp.status_code == 503
    assert resp.json()["ready"] is False


def test_health_tetap_tanpa_cek_dependency():
    """/health = liveness murni; tak boleh ikut jatuh saat dependency hilang."""
    assert client.get("/health").json() == {"status": "ok"}


# --- Structured logging ------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_context():
    logging_config.reset_context()
    yield
    # Konteks job adalah contextvar proses — bersihkan supaya tak bocor antar tes.
    logging_config.reset_context()


def _format_json(record: logging.LogRecord) -> dict:
    fmt = logging_config._JsonFormatter()
    logging_config._JobContextFilter().filter(record)
    return json.loads(fmt.format(record))


def test_json_log_membawa_konteks_job():
    logging_config.bind_job_context("job-123", "usr-9")
    logging_config.set_stage("llm")
    record = logging.makeLogRecord({"msg": "menyusun isi", "levelname": "INFO", "name": "x"})

    payload = _format_json(record)
    assert payload["message"] == "menyusun isi"
    assert payload["job_id"] == "job-123"
    assert payload["owner"] == "usr-9"
    assert payload["stage"] == "llm"


def test_json_log_menyertakan_field_extra():
    """Field extra={...} (mis. duration_ms untuk metrik) ikut tanpa didaftarkan."""
    record = logging.makeLogRecord(
        {"msg": "selesai", "levelname": "INFO", "name": "x",
         "event": "job_finished", "duration_ms": 1234, "outcome": "done"}
    )
    payload = _format_json(record)
    assert payload["event"] == "job_finished"
    assert payload["duration_ms"] == 1234
    assert payload["outcome"] == "done"


def test_konteks_kosong_tak_menaruh_field_job():
    """Baris log di luar job (startup, request biasa) tak membawa field job kosong."""
    record = logging.makeLogRecord({"msg": "boot", "levelname": "INFO", "name": "x"})
    payload = _format_json(record)
    assert "job_id" not in payload and "owner" not in payload and "stage" not in payload


# --- Sentry seam -------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_sentry():
    telemetry.reset_for_test()
    yield
    telemetry.reset_for_test()


def test_sentry_mati_default(monkeypatch):
    monkeypatch.setattr(config, "SENTRY_DSN", None)
    assert telemetry.sentry_enabled() is False
    assert telemetry.init_sentry() is False


def test_capture_exception_no_op_saat_mati(monkeypatch):
    """Reporter yang mati tak boleh melempar — kalau tidak, dia menutupi kegagalan
    asli yang sedang dilaporkan."""
    monkeypatch.setattr(config, "SENTRY_DSN", None)
    telemetry.init_sentry()
    telemetry.capture_exception(RuntimeError("boom"))  # tak boleh raise


def test_init_gagal_lunak_saat_paket_tak_ada(monkeypatch):
    """DSN diisi tapi sentry-sdk tak terpasang: peringatan, bukan crash boot."""
    try:
        import sentry_sdk  # noqa: F401
        pytest.skip("sentry-sdk terpasang di lingkungan ini; jalur paket-hilang tak berlaku")
    except ModuleNotFoundError:
        pass
    monkeypatch.setattr(config, "SENTRY_DSN", "https://k@example.com/1")
    assert telemetry.init_sentry() is False
