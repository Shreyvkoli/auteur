from fastapi import APIRouter, HTTPException, status, Depends, Request, Header
from pydantic import BaseModel
from typing import Optional, List
from core.database import get_supabase
from core.security import get_current_user, get_optional_user
from core.config import settings
import hmac
import hashlib
import json
import logging

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)


class PlanResponse(BaseModel):
    id: str
    name: str
    price_inr: int
    price_usd: int
    video_limit: int
    vault_limit: int
    features: List[str]


class CreateOrderRequest(BaseModel):
    plan_id: str
    currency: str = "INR"


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str


class SubscriptionResponse(BaseModel):
    plan: str
    videos_used: int
    video_limit: int
    vault_limit: int
    status: str


@router.get("/plans", response_model=List[PlanResponse])
async def get_plans():
    supabase = get_supabase()
    plans = supabase.table("plans").select("*").order("price_usd").execute()
    return plans.data


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    user = supabase.table("users").select("plan, videos_used_this_month").eq("id", current_user["id"]).single().execute()
    
    if not user.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    plan = supabase.table("plans").select("*").eq("name", user.data["plan"]).single().execute()
    
    return SubscriptionResponse(
        plan=user.data["plan"],
        videos_used=user.data["videos_used_this_month"],
        video_limit=plan.data["video_limit"] if plan.data else 3,
        vault_limit=plan.data["vault_limit"] if plan.data else 10,
        status="active"
    )


@router.post("/razorpay/create-order", response_model=CreateOrderResponse)
async def create_razorpay_order(
    request: CreateOrderRequest,
    current_user: dict = Depends(get_current_user)
):
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise HTTPException(status_code=500, detail="Razorpay not configured")
    
    supabase = get_supabase()
    plan = supabase.table("plans").select("*").eq("id", request.plan_id).single().execute()
    
    if not plan.data:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    import razorpay
    client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
    
    amount = plan.data["price_inr"] if request.currency == "INR" else plan.data["price_usd"] * 100
    
    order = client.order.create({
        "amount": amount,
        "currency": request.currency,
        "receipt": f"plan_{request.plan_id}_{current_user['id']}",
        "notes": {
            "user_id": current_user["id"],
            "plan_id": request.plan_id
        }
    })
    
    return CreateOrderResponse(
        order_id=order["id"],
        amount=order["amount"],
        currency=order["currency"],
        key_id=settings.razorpay_key_id
    )


@router.post("/stripe/create-checkout")
async def create_stripe_checkout(
    request: CreateOrderRequest,
    current_user: dict = Depends(get_current_user)
):
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    supabase = get_supabase()
    plan = supabase.table("plans").select("*").eq("id", request.plan_id).single().execute()
    
    if not plan.data:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    import stripe
    stripe.api_key = settings.stripe_secret_key
    
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": request.currency.lower(),
                "product_data": {"name": plan.data["name"]},
                "unit_amount": plan.data["price_usd"] * 100 if request.currency == "USD" else plan.data["price_inr"] * 100,
                "recurring": {"interval": "month"}
            },
            "quantity": 1
        }],
        mode="subscription",
        success_url=f"{settings.frontend_url}/profile?success=true",
        cancel_url=f"{settings.frontend_url}/profile?canceled=true",
        metadata={
            "user_id": current_user["id"],
            "plan_id": request.plan_id
        }
    )
    
    return {"checkout_url": session.url}


@router.post("/razorpay/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None)
):
    if not settings.razorpay_webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    
    body = await request.body()
    
    expected_signature = hmac.new(
        settings.razorpay_webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_signature, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    payload = json.loads(body)
    event = payload.get("event")
    
    if event == "payment.captured":
        payment = payload["payload"]["payment"]["entity"]
        user_id = payment["notes"].get("user_id")
        plan_id = payment["notes"].get("plan_id")
        
        if user_id and plan_id:
            supabase = get_supabase()
            plan = supabase.table("plans").select("*").eq("id", plan_id).single().execute()
            
            if plan.data:
                supabase.table("users").update({"plan": plan.data["name"]}).eq("id", user_id).execute()
                
                supabase.table("payments").insert({
                    "user_id": user_id,
                    "plan_id": plan_id,
                    "amount": payment["amount"],
                    "currency": payment["currency"],
                    "provider": "razorpay",
                    "status": "completed"
                }).execute()
    
    return {"status": "ok"}


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None)
):
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    
    import stripe
    stripe.api_key = settings.stripe_secret_key
    
    body = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            body, stripe_signature, settings.stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session["metadata"].get("user_id")
        plan_id = session["metadata"].get("plan_id")
        
        if user_id and plan_id:
            supabase = get_supabase()
            plan = supabase.table("plans").select("*").eq("id", plan_id).single().execute()
            
            if plan.data:
                supabase.table("users").update({"plan": plan.data["name"]}).eq("id", user_id).execute()
                
                supabase.table("payments").insert({
                    "user_id": user_id,
                    "plan_id": plan_id,
                    "amount": session["amount_total"],
                    "currency": session["currency"],
                    "provider": "stripe",
                    "status": "completed"
                }).execute()
    
    return {"status": "ok"}


@router.get("/history")
async def get_payment_history(current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    payments = supabase.table("payments").select("*").eq("user_id", current_user["id"]).order("created_at", desc=True).execute()
    return payments.data