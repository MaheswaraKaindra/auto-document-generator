"""Endpoint Billing dan Kuota (Peran 3 — Backend & Templating).

Menyediakan API untuk melihat pemakaian kuota, estimasi biaya LLM,
membuat session Stripe Checkout untuk upgrade tier, dan webhook Stripe.
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.api.deps import get_current_user
from app.services import billing_service
from app.services.auth_service import Principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/usage")
def get_usage_summary(principal: Principal = Depends(get_current_user)):
    """Mengembalikan ringkasan kuota & pemakaian token LLM milik pengguna saat ini."""
    return billing_service.get_user_usage_summary(principal.id)


@router.post("/checkout")
def create_checkout_session(principal: Principal = Depends(get_current_user)):
    """Membuat session Stripe Checkout untuk upgrade paket Pro."""
    try:
        return billing_service.create_stripe_checkout_session(
            owner=principal.id, user_email=principal.email
        )
    except ValueError as e:
        # Pesan konfigurasi yang KITA tulis sendiri (mis. STRIPE_PRO_PRICE_ID
        # kosong) — aman ditampilkan, dan justru itu yang menolong operator.
        logger.exception("Konfigurasi Stripe belum lengkap")
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        # Exception Stripe TIDAK diteruskan apa adanya: isinya bisa memuat request
        # id, potongan parameter, dan detail akun yang tak ada gunanya bagi
        # pengguna. Sebab aslinya tetap utuh di log server.
        logger.exception("Gagal membuat Stripe checkout session")
        raise HTTPException(
            status_code=502,
            detail="Gagal menghubungi Stripe. Coba lagi beberapa saat lagi; "
                   "kalau terus terjadi, hubungi pengelola aplikasi.",
        ) from e


@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    """Handler Webhook event dari Stripe (misal: checkout.session.completed)."""
    payload = await request.body()
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Header stripe-signature wajib ada.")

    success, message = billing_service.handle_stripe_webhook(payload, stripe_signature)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"status": "success", "detail": message}
