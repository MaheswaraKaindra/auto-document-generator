"""Layanan Billing, Metering, dan Integrasi Stripe (Peran 3 — Backend).

Mengelola pencatatan pemakaian token LLM & estimasi biaya per akun,
penegakan kuota paket (Free vs Pro), dan integrasi pembayaran Stripe.

Menggunakan SQLite `config.DATABASE_PATH` yang sama dengan `job_store.py`.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import stripe

from app.core import config
from app.services import auth_service
from app.services.auth_service import Principal

logger = logging.getLogger(__name__)

DB_PATH = Path(config.DATABASE_PATH)

TIER_FREE = "free"
TIER_PRO = "pro"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_subscriptions (
    owner                  TEXT PRIMARY KEY,
    tier                   TEXT NOT NULL DEFAULT 'free',
    stripe_customer_id     TEXT,
    stripe_subscription_id TEXT,
    status                 TEXT NOT NULL DEFAULT 'active',
    created_at             TEXT NOT NULL,
    updated_at             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_records (
    id                 TEXT PRIMARY KEY,
    owner              TEXT NOT NULL,
    job_id             TEXT NOT NULL,
    doc_type           TEXT NOT NULL,
    input_tokens       INTEGER NOT NULL DEFAULT 0,
    output_tokens      INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens  INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd REAL NOT NULL DEFAULT 0.0,
    created_at         TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_billing_db() -> None:
    """Inisialisasi tabel billing jika belum ada."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def get_user_tier(owner: str) -> str:
    """Mengambil tier aktif milik `owner` ('free' atau 'pro')."""
    if not owner or owner == "anonymous":
        return TIER_FREE

    with _connect() as conn:
        row = conn.execute(
            "SELECT tier, status FROM user_subscriptions WHERE owner = ?", (owner,)
        ).fetchone()
        if row and row["status"] in ("active", "trialing"):
            return row["tier"]
    return TIER_FREE


def set_user_tier(
    owner: str,
    tier: str,
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    status: str = "active",
) -> None:
    """Meng-update atau membuat entri langganan pengguna."""
    now = _now_iso()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO user_subscriptions
                (owner, tier, stripe_customer_id, stripe_subscription_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(owner) DO UPDATE SET
                tier = excluded.tier,
                stripe_customer_id = COALESCE(excluded.stripe_customer_id, user_subscriptions.stripe_customer_id),
                stripe_subscription_id = COALESCE(excluded.stripe_subscription_id, user_subscriptions.stripe_subscription_id),
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (owner, tier, stripe_customer_id, stripe_subscription_id, status, now, now),
        )


def calculate_llm_cost_usd(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Menghitung estimasi biaya USD berdasarkan tarif Anthropic Claude Sonnet 5:
    - Input: $3.00 / 1M token
    - Output: $15.00 / 1M token
    - Cache Write: $3.75 / 1M token
    - Cache Read: $0.30 / 1M token
    """
    cost_input = (input_tokens / 1_000_000.0) * 3.00
    cost_output = (output_tokens / 1_000_000.0) * 15.00
    cost_cache_write = (cache_write_tokens / 1_000_000.0) * 3.75
    cost_cache_read = (cache_read_tokens / 1_000_000.0) * 0.30
    return round(cost_input + cost_output + cost_cache_write + cost_cache_read, 6)


def record_job_usage(
    owner: str,
    job_id: str,
    doc_type: str,
    usage_dict: dict,
) -> Dict[str, Any]:
    """Mencatat pemakaian token & estimasi biaya untuk job yang selesai."""
    input_tokens = usage_dict.get("input_tokens", 0)
    output_tokens = usage_dict.get("output_tokens", 0)
    cache_read_tokens = usage_dict.get("cache_read_input_tokens", 0)
    cache_write_tokens = usage_dict.get("cache_creation_input_tokens", 0)

    cost_usd = calculate_llm_cost_usd(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )

    record_id = str(uuid.uuid4())
    now = _now_iso()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO usage_records
                (id, owner, job_id, doc_type, input_tokens, output_tokens,
                 cache_read_tokens, cache_write_tokens, estimated_cost_usd, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                owner,
                job_id,
                doc_type,
                input_tokens,
                output_tokens,
                cache_read_tokens,
                cache_write_tokens,
                cost_usd,
                now,
            ),
        )

    return {
        "id": record_id,
        "owner": owner,
        "job_id": job_id,
        "doc_type": doc_type,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": cost_usd,
    }


def get_user_usage_summary(owner: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Menghitung ringkasan pemakaian akun dalam 30 hari terakhir."""
    tier = get_user_tier(owner)
    limit = config.TIER_PRO_LIMIT if tier == TIER_PRO else config.TIER_FREE_LIMIT

    ref_time = now or datetime.now(timezone.utc)
    start_window = (ref_time - timedelta(days=30)).isoformat()

    with _connect() as conn:
        # Hitung jumlah generate job dalam 30 hari terakhir
        count_row = conn.execute(
            "SELECT COUNT(*) as count FROM jobs WHERE owner = ? AND created_at >= ?",
            (owner, start_window),
        ).fetchone()
        jobs_used = count_row["count"] if count_row else 0

        # Hitung total token & estimasi biaya
        usage_row = conn.execute(
            """
            SELECT
                COALESCE(SUM(input_tokens), 0) as total_input,
                COALESCE(SUM(output_tokens), 0) as total_output,
                COALESCE(SUM(cache_read_tokens), 0) as total_cache_read,
                COALESCE(SUM(cache_write_tokens), 0) as total_cache_write,
                COALESCE(SUM(estimated_cost_usd), 0.0) as total_cost
            FROM usage_records
            WHERE owner = ? AND created_at >= ?
            """,
            (owner, start_window),
        ).fetchone()

        total_input = usage_row["total_input"] if usage_row else 0
        total_output = usage_row["total_output"] if usage_row else 0
        total_cache_read = usage_row["total_cache_read"] if usage_row else 0
        total_cache_write = usage_row["total_cache_write"] if usage_row else 0
        total_cost = usage_row["total_cost"] if usage_row else 0.0

    remaining = max(0, limit - jobs_used) if limit > 0 else 999999

    return {
        "owner": owner,
        "tier": tier,
        "limit": limit,
        "jobs_used": jobs_used,
        "remaining": remaining,
        "total_tokens": total_input + total_output + total_cache_read + total_cache_write,
        "total_cost_usd": round(total_cost, 4),
        "window_days": 30,
    }


def check_quota_available(
    caller: Principal, now: Optional[datetime] = None
) -> Tuple[bool, int, int, str]:
    """Memeriksa apakah pemanggil memiliki sisa kuota.
    
    Returns:
        (allowed: bool, limit: int, used: int, reason: str)
    """
    # Mode Dev (Auth non-aktif) atau Anonymous -> Tidak dibatasi
    if not auth_service.auth_enabled() or caller.is_anonymous:
        return True, 0, 0, "Dev/Anonymous mode — kuota tidak dibatasi"

    summary = get_user_usage_summary(caller.id, now=now)
    tier = summary["tier"]
    limit = summary["limit"]
    used = summary["jobs_used"]

    if limit > 0 and used >= limit:
        return (
            False,
            limit,
            used,
            f"Kuota tier {tier.upper()} Anda habis ({used}/{limit} dokumen dalam 30 hari). "
            f"Silakan upgrade ke Pro untuk melanjutkan.",
        )

    return True, limit, used, "Kuota tersedia"


def create_stripe_checkout_session(
    owner: str, user_email: Optional[str] = None
) -> Dict[str, str]:
    """Membuat Stripe Checkout Session untuk upgrade paket Pro."""
    success_url = f"{config.FRONTEND_URL.rstrip('/')}/?billing=success"
    cancel_url = f"{config.FRONTEND_URL.rstrip('/')}/?billing=cancel"

    if not config.STRIPE_SECRET_KEY:
        # Stub / Mock mode untuk testing tanpa Stripe API key sungguhan
        logger.info("STRIPE_SECRET_KEY tidak disetel — menggunakan mode Checkout Stub.")
        return {
            "checkout_url": f"{config.FRONTEND_URL.rstrip('/')}/?billing=success_stub&owner={owner}",
            "session_id": f"cs_test_mock_{uuid.uuid4().hex[:12]}",
            "is_stub": True,
        }

    stripe.api_key = config.STRIPE_SECRET_KEY

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price": config.STRIPE_PRO_PRICE_ID,
                "quantity": 1,
            }
        ],
        mode="subscription",
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=user_email,
        client_reference_id=owner,
        metadata={"owner": owner},
    )

    return {
        "checkout_url": session.url,
        "session_id": session.id,
        "is_stub": False,
    }


def handle_stripe_webhook(payload: bytes, sig_header: str) -> Tuple[bool, str]:
    """Memproses webhook event dari Stripe."""
    if not config.STRIPE_WEBHOOK_SECRET or not config.STRIPE_SECRET_KEY:
        # Jika Stripe tidak dikonfigurasi, beri fallback aman
        return False, "Stripe secret belum dikonfigurasi"

    stripe.api_key = config.STRIPE_SECRET_KEY
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, config.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.error("Gagal memverifikasi webhook Stripe: %s", e)
        return False, f"Invalid signature: {e}"

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})

    logger.info("Stripe Webhook diterima: %s", event_type)

    if event_type in ("checkout.session.completed", "customer.subscription.created"):
        owner = data_object.get("client_reference_id") or data_object.get("metadata", {}).get("owner")
        cust_id = data_object.get("customer")
        sub_id = data_object.get("subscription") or data_object.get("id")

        if owner:
            set_user_tier(
                owner=owner,
                tier=TIER_PRO,
                stripe_customer_id=cust_id,
                stripe_subscription_id=sub_id,
                status="active",
            )
            logger.info("Tier pengguna %s dinaikkan ke PRO via Stripe", owner)

    elif event_type in ("customer.subscription.deleted", "customer.subscription.updated"):
        status = data_object.get("status")
        sub_id = data_object.get("id")
        owner = data_object.get("metadata", {}).get("owner")

        if not owner:
            # Cari owner berdasarkan subscription_id
            with _connect() as conn:
                row = conn.execute(
                    "SELECT owner FROM user_subscriptions WHERE stripe_subscription_id = ?",
                    (sub_id,),
                ).fetchone()
                if row:
                    owner = row["owner"]

        if owner:
            new_tier = TIER_PRO if status in ("active", "trialing") else TIER_FREE
            set_user_tier(owner=owner, tier=new_tier, status=status or "canceled")
            logger.info("Status langganan pengguna %s diperbarui: %s (%s)", owner, status, new_tier)

    return True, f"Event {event_type} diproses."
