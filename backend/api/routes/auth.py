from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from core.database import get_supabase, get_supabase_anon
from core.security import create_access_token, get_current_user
from core.config import settings
import logging
from datetime import datetime

DEV_MODE = settings.dev_mode

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class OAuthRequest(BaseModel):
    provider: str
    redirect_url: Optional[str] = None


class AuthResponse(BaseModel):
    user: dict
    access_token: str
    refresh_token: str


@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignUpRequest):
    if DEV_MODE:
        user_id = f"dev_{request.email.replace('@', '_at_')}"
        user_data = {
            "id": user_id,
            "email": request.email,
            "name": request.name or request.email.split("@")[0],
            "avatar_url": None,
            "plan": "free",
            "videos_used_this_month": 0,
            "style_dna": None,
        }
        supabase = get_supabase()
        supabase.table("users").upsert(user_data).execute()
        access_token = create_access_token({"sub": user_id})
        return AuthResponse(
            user=user_data,
            access_token=access_token,
            refresh_token=f"dev_refresh_{user_id}",
        )

    supabase = get_supabase_anon()
    try:
        response = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password,
            "options": {
                "data": {"name": request.name} if request.name else {},
                "email_redirect_to": f"{settings.frontend_url}/auth/callback"
            }
        })
        
        if response.user is None:
            raise HTTPException(status_code=400, detail="Signup failed")
        
        user_data = {
            "id": response.user.id,
            "email": response.user.email,
            "name": request.name,
            "avatar_url": response.user.user_metadata.get("avatar_url"),
            "plan": "free",
            "videos_used_this_month": 0,
            "style_dna": None
        }
        
        supabase_admin = get_supabase()
        supabase_admin.table("users").upsert(user_data).execute()
        
        access_token = create_access_token({"sub": response.user.id})
        
        return AuthResponse(
            user=user_data,
            access_token=access_token,
            refresh_token=response.session.refresh_token if response.session else ""
        )
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/signin", response_model=AuthResponse)
async def signin(request: SignInRequest):
    if DEV_MODE:
        user_id = f"dev_{request.email.replace('@', '_at_')}"
        supabase = get_supabase()
        user = supabase.table("users").select("*").eq("id", user_id).single().execute()
        if not user.data:
            raise HTTPException(status_code=401, detail="Invalid credentials (dev mode: sign up first)")
        access_token = create_access_token({"sub": user_id})
        return AuthResponse(
            user=user.data,
            access_token=access_token,
            refresh_token=f"dev_refresh_{user_id}",
        )

    supabase = get_supabase_anon()
    try:
        response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        
        if response.user is None or response.session is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        supabase_admin = get_supabase()
        user = supabase_admin.table("users").select("*").eq("id", response.user.id).single().execute()
        
        if not user.data:
            user_data = {
                "id": response.user.id,
                "email": response.user.email,
                "name": response.user.user_metadata.get("name"),
                "avatar_url": response.user.user_metadata.get("avatar_url"),
                "plan": "free",
                "videos_used_this_month": 0,
                "style_dna": None
            }
            supabase_admin.table("users").upsert(user_data).execute()
            user_data_obj = user_data
        else:
            user_data_obj = user.data
        
        access_token = create_access_token({"sub": response.user.id})
        
        return AuthResponse(
            user=user_data_obj,
            access_token=access_token,
            refresh_token=response.session.refresh_token
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signin error: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/oauth", response_model=AuthResponse)
async def oauth(request: OAuthRequest):
    supabase = get_supabase_anon()
    try:
        if request.provider not in ["google", "github"]:
            raise HTTPException(status_code=400, detail="Unsupported provider")
        
        response = supabase.auth.sign_in_with_oauth({
            "provider": request.provider,
            "options": {
                "redirect_to": request.redirect_url or f"{settings.frontend_url}/auth/callback"
            }
        })
        
        if response.url:
            return {"url": response.url}
        
        raise HTTPException(status_code=400, detail="OAuth failed")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    supabase = get_supabase_anon()
    try:
        response = supabase.auth.refresh_session(refresh_token)
        if response.session is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        access_token = create_access_token({"sub": response.user.id})
        return {"access_token": access_token, "refresh_token": response.session.refresh_token}
    except Exception as e:
        logger.error(f"Refresh token error: {e}")
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.post("/signout")
async def signout(current_user: dict = Depends(get_current_user)):
    supabase = get_supabase_anon()
    try:
        supabase.auth.sign_out()
        return {"message": "Signed out successfully"}
    except Exception as e:
        logger.error(f"Signout error: {e}")
        raise HTTPException(status_code=400, detail=str(e))