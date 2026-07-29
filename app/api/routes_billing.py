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
        session_info = billing_service.create_stripe_checkout_session(
            owner=principal.id, user_email=principal.email
        )
        return session_info
    except Exception as e:
        logger.exception("Gagal membuat Stripe checkout session")
        raise HTTPException(
            status_code=500, detail=f"Gagal memproses Checkout Stripe: {e}"
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
