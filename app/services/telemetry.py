"""Error tracking (Sentry) sebagai SEAM opsional (#14).

`SENTRY_DSN` kosong → mati total: `sentry_sdk` tak pernah di-import, `init()` &
`capture_exception()` jadi no-op. Pola yang sama persis dengan `job_queue`
(REDIS_URL) dan `auth_service` (SUPABASE_URL) — "punya error tracking" jadi
keputusan deploy, bukan dependency yang mengikat dev/test/demo $0.

Kenapa dibungkus, bukan `sentry_sdk.init` langsung di main.py: dua pemanggil
(web + worker) butuh init yang sama, error saat mengirim ke Sentry TIDAK boleh
menular ke pipeline (menangkap error lalu gagal karena reporter-nya sendiri
adalah kegagalan yang lebih buruk dari yang dilaporkan), dan test harus bisa
memverifikasi jalur mati tanpa memasang paket apa pun.
"""

from __future__ import annotations

import logging

from app.core import config
from app.core.logging_config import current_context

logger = logging.getLogger(__name__)

_initialized = False


def sentry_enabled() -> bool:
    """Dibaca saat dipanggil (tak di-cache) supaya test bisa menyetel DSN."""
    return bool(config.SENTRY_DSN)


def init_sentry() -> bool:
    """Aktifkan Sentry kalau DSN ada & paketnya terpasang. Kembalikan status.

    Gagal-lunak dengan sengaja: DSN diisi tapi `sentry-sdk` tak terpasang tak
    boleh menggagalkan boot — di-log sekali sebagai peringatan, lalu lanjut tanpa
    error tracking. Kehilangan observability lebih ringan daripada layanan mati.
    """
    global _initialized
    if _initialized or not sentry_enabled():
        return _initialized
    try:
        import sentry_sdk                              # noqa: PLC0415

        sentry_sdk.init(
            dsn=config.SENTRY_DSN,
            environment=config.SENTRY_ENVIRONMENT,
            # Angka konservatif: kirim jejak performa 10% request. Naikkan lewat
            # dashboard/env kalau perlu; default rendah supaya tak diam-diam mahal.
            traces_sample_rate=0.1,
        )
        _initialized = True
        logger.info("Sentry aktif (environment=%s)", config.SENTRY_ENVIRONMENT)
    except ModuleNotFoundError:
        logger.warning(
            "SENTRY_DSN diisi tapi paket 'sentry-sdk' tak terpasang — error "
            "tracking dilewati. Tambahkan sentry-sdk ke requirements untuk "
            "mengaktifkannya."
        )
    except Exception:
        logger.warning("Gagal menginisialisasi Sentry — dilanjutkan tanpa error tracking",
                       exc_info=True)
    return _initialized


def capture_exception(exc: BaseException) -> None:
    """Kirim exception ke Sentry dengan konteks job (job_id/owner/stage) sebagai
    tag. No-op kalau Sentry mati. TAK PERNAH melempar — reporter yang meledak
    tak boleh menutupi kegagalan asli yang sedang dilaporkan."""
    if not _initialized:
        return
    try:
        import sentry_sdk                              # noqa: PLC0415

        with sentry_sdk.push_scope() as scope:
            for key, value in current_context().items():
                scope.set_tag(key, value)
            sentry_sdk.capture_exception(exc)
    except Exception:
        logger.warning("Gagal mengirim exception ke Sentry", exc_info=True)


def reset_for_test() -> None:
    """Kembalikan state modul ke awal. Untuk test yang menyalakan/mematikan DSN."""
    global _initialized
    _initialized = False
