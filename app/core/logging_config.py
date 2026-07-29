"""Logging terstruktur + konteks per-job (#14).

DUA hal digabung di sini karena saling melengkapi:

1. **Format** — `LOG_FORMAT=json` memancarkan satu objek JSON per baris (siap
   diagregasi Loki/CloudWatch/dst.), default `plain` tetap enak dibaca manusia
   saat `uvicorn --reload`. Seam yang sama dengan yang lain: nilai tak dikenal
   jatuh ke plain, jadi salah-ketik tak pernah MEMATIKAN log.

2. **Konteks** — `job_id`/`owner`/`stage` menempel di SETIAP baris log yang
   dipancarkan selama sebuah job berjalan, tanpa tiap pemanggil `logger.info`
   harus mengoper ketiganya. Caranya `contextvars` (bukan thread-local): benar
   di async FastAPI DAN di worker RQ, dan otomatis terisolasi antar job.

Kenapa contextvar + filter, bukan `logger.info(..., extra=...)` di tiap titik:
`extra` harus diulang di setiap panggilan dan diam-diam hilang di log pihak
ketiga (uvicorn, rq). Filter yang membaca contextvar menempelkannya ke SEMUA
record — termasuk yang bukan kita yang menulis — jadi jejak sebuah job utuh.
"""

from __future__ import annotations

import contextvars
import datetime as _dt
import json
import logging
from typing import Any, Optional

from app.core import config

# Konteks job yang sedang diproses proses/task ini. Default kosong = baris log
# di luar job (startup, request biasa) tak membawa field yang tak relevan.
_job_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("job_id", default=None)
_owner: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("owner", default=None)
_stage: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("stage", default=None)

# Atribut LogRecord bawaan — dipakai untuk memisahkan field `extra` buatan
# pemanggil dari metadata standar saat memformat JSON.
_STD_ATTRS = frozenset(
    logging.makeLogRecord({}).__dict__.keys()
) | {"message", "asctime", "taskName"}


def bind_job_context(job_id: Optional[str] = None, owner: Optional[str] = None) -> None:
    """Tautkan job_id/owner ke seluruh log berikutnya di konteks ini.

    Dipanggil sekali di awal `_run_generation`. Di worker RQ tiap job punya
    konteks sendiri; di mode inline (BackgroundTasks) task berikutnya menimpa,
    jadi tak ada kebocoran antar job selama binding dilakukan di awal tiap job.
    """
    if job_id is not None:
        _job_id.set(job_id)
    if owner is not None:
        _owner.set(owner)


def reset_context() -> None:
    """Kosongkan seluruh konteks job. Beda dari `bind_job_context(None, None)` yang
    sengaja mengabaikan None (supaya bind parsial tak menimpa) — ini benar-benar
    membersihkan, untuk teardown test atau akhir sebuah job."""
    _job_id.set(None)
    _owner.set(None)
    _stage.set(None)


def set_stage(stage: Optional[str]) -> None:
    """Tandai tahap pipeline yang sedang jalan (ingest/parse/llm/render/export).
    Muncul di log DAN di konteks error Sentry, jadi "gagal di tahap mana"
    terjawab tanpa menebak dari pesan."""
    _stage.set(stage)


def current_context() -> dict[str, Any]:
    """Snapshot konteks job aktif. Dipakai telemetry untuk memberi tag error."""
    ctx: dict[str, Any] = {}
    if (jid := _job_id.get()) is not None:
        ctx["job_id"] = jid
    if (owner := _owner.get()) is not None:
        ctx["owner"] = owner
    if (stage := _stage.get()) is not None:
        ctx["stage"] = stage
    return ctx


class _JobContextFilter(logging.Filter):
    """Tempelkan konteks job ke tiap record supaya formatter bisa memancarkannya."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in current_context().items():
            setattr(record, key, value)
        return True


class _JsonFormatter(logging.Formatter):
    """Satu objek JSON per baris: timestamp, level, logger, message, + konteks
    job & field `extra` apa pun. Exception disertakan sebagai teks traceback."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": _dt.datetime.fromtimestamp(
                record.created, _dt.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("job_id", "owner", "stage"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        # Field extra={...} dari pemanggil (mis. duration_ms) ikut, tanpa perlu
        # didaftarkan di sini — apa pun yang bukan atribut standar LogRecord.
        for key, value in record.__dict__.items():
            if key not in _STD_ATTRS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    """Pasang handler root sesuai LOG_FORMAT/LOG_LEVEL. Idempoten — aman dipanggil
    di main.py (web) DAN app/worker.py (worker), yang bisa jadi proses berbeda."""
    root = logging.getLogger()
    root.setLevel(config.LOG_LEVEL.upper())

    handler = logging.StreamHandler()
    handler.addFilter(_JobContextFilter())
    if config.LOG_FORMAT.lower() == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        ))

    # Ganti handler kita saja; jangan hapus milik uvicorn yang mungkin sudah ada.
    for existing in list(root.handlers):
        if getattr(existing, "_adg_observability", False):
            root.removeHandler(existing)
    handler._adg_observability = True  # type: ignore[attr-defined]
    root.addHandler(handler)
