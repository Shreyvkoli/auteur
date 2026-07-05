from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from core.config import settings
from core.database import get_supabase

security = HTTPBearer(auto_error=False)

# Dev mode: single source of truth from config
DEV_MODE = settings.dev_mode


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=7))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.app_secret_key, algorithm="HS256")


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


DEV_USER = {
    "id": settings.dev_user_id,
    "email": settings.dev_user_email,
    "name": settings.dev_user_name,
    "plan": settings.dev_user_plan,
    "videos_used_this_month": 0,
    "style_dna": None,
}


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    if DEV_MODE:
        return DEV_USER

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = verify_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    supabase = get_supabase()
    user = supabase.table("users").select("*").eq("id", user_id).single().execute()
    if not user.data:
        raise HTTPException(status_code=401, detail="User not found")
    return user.data


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    if DEV_MODE:
        return DEV_USER
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None