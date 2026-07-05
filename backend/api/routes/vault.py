import os
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from uuid import uuid4
from core.database import get_supabase
from core.security import get_current_user
from services.r2 import generate_presigned_upload_url, generate_presigned_download_url, delete_from_r2
import logging

router = APIRouter(prefix="/vault", tags=["vault"])
logger = logging.getLogger(__name__)

ALLOWED_TYPES = {
    "meme": {"video/mp4", "video/quicktime", "video/x-msvideo"},
    "sound": {"audio/mpeg", "audio/wav", "audio/mp4", "audio/ogg"},
    "music": {"audio/mpeg", "audio/wav", "audio/mp4", "audio/ogg"},
    "preset": {"application/json"}
}

MAX_FILE_SIZES = {
    "meme": 50 * 1024 * 1024,
    "sound": 10 * 1024 * 1024,
    "music": 50 * 1024 * 1024,
    "preset": 1 * 1024 * 1024
}


class VaultItemResponse(BaseModel):
    id: str
    type: str
    name: str
    r2_url: str
    created_at: str


class VaultListResponse(BaseModel):
    items: List[VaultItemResponse]
    total: int

class VaultUploadInitRequest(BaseModel):
    type: str
    filename: str
    content_type: str
    size: int
    name: str


class VaultUploadInitResponse(BaseModel):
    item_id: str
    upload_url: str
    fields: dict


@router.post("/")
async def upload_vault_item(
    file: UploadFile = File(...),
    type: str = Form("meme"),
    name: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    """Direct file upload to vault (dev mode)."""
    from uuid import uuid4
    from datetime import datetime

    item_id = str(uuid4())
    allowed_types = {"meme", "sound", "music", "preset"}
    if type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Invalid vault item type: {type}")

    ext = os.path.splitext(file.filename or "file")[1] or ""
    key = f"vault/{current_user['id']}/{type}/{item_id}{ext}"

    content = await file.read()
    from services.r2 import upload_to_r2
    local_path = None
    try:
        upload_to_r2(key, content, file.content_type or "application/octet-stream")
    except Exception as e:
        logger.warning(f"R2 upload failed, saving locally: {e}")
        local_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "dev_uploads", "vault", f"{item_id}{ext}"
        )
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(content)

    supabase = get_supabase()
    supabase.table("vault_items").insert({
        "id": item_id,
        "user_id": current_user["id"],
        "type": type,
        "name": name or file.filename or "untitled",
        "r2_url": local_path or key,
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    return VaultItemResponse(
        id=item_id,
        type=type,
        name=name or file.filename or "untitled",
        r2_url=local_path or key,
        created_at=datetime.utcnow().isoformat(),
    )


@router.get("/", response_model=VaultListResponse)
async def list_vault_items(
    type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    supabase = get_supabase()
    query = supabase.table("vault_items").select("*", count="exact").eq("user_id", current_user["id"])
    
    if type:
        query = query.eq("type", type)
    
    items = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    
    result = []
    for item in (items.data or []):
        r2_key = item.get("r2_url", "")
        try:
            url = generate_presigned_download_url(r2_key)
        except Exception as e:
            logger.warning(f"Failed to generate download URL for {r2_key}: {e}")
            url = r2_key
        result.append(VaultItemResponse(
            id=item["id"],
            type=item["type"],
            name=item["name"],
            r2_url=url,
            created_at=item["created_at"]
        ))
    return VaultListResponse(items=result, total=items.count or 0)


@router.post("/upload/init", response_model=VaultUploadInitResponse)
async def init_vault_upload(
    request: VaultUploadInitRequest,
    current_user: dict = Depends(get_current_user)
):
    if request.type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Invalid vault item type")
    
    if request.content_type not in ALLOWED_TYPES[request.type]:
        raise HTTPException(status_code=400, detail=f"Invalid file type for {request.type}")
    
    max_size = MAX_FILE_SIZES.get(request.type, 10 * 1024 * 1024)
    if request.size > max_size:
        raise HTTPException(status_code=400, detail=f"File size exceeds limit for {request.type}")
    
    supabase = get_supabase()
    user_data = supabase.table("users").select("plan, vault_limit").eq("id", current_user["id"]).single().execute()
    
    if user_data.data:
        vault_limit = user_data.data.get("vault_limit", 10)
        if vault_limit != -1:
            count = supabase.table("vault_items").select("id", count="exact").eq("user_id", current_user["id"]).execute()
            if count.count >= vault_limit:
                raise HTTPException(status_code=403, detail=f"Vault limit reached ({vault_limit} items). Upgrade to add more.")
    
    item_id = str(uuid4())
    file_ext = request.filename.split(".")[-1].lower()
    r2_key = f"vault/{current_user['id']}/{request.type}/{item_id}.{file_ext}"
    
    presigned = generate_presigned_upload_url(r2_key, request.content_type)
    
    supabase.table("vault_items").insert({
        "id": item_id,
        "user_id": current_user["id"],
        "type": request.type,
        "name": request.name,
        "r2_url": r2_key
    }).execute()
    
    return VaultUploadInitResponse(
        item_id=item_id,
        upload_url=presigned["url"],
        fields=presigned["fields"]
    )


@router.post("/upload/complete")
async def complete_vault_upload(
    item_id: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    supabase = get_supabase()
    item = supabase.table("vault_items").select("*").eq("id", item_id).eq("user_id", current_user["id"]).single().execute()
    
    if not item.data:
        raise HTTPException(status_code=404, detail="Vault item not found")
    
    return {"item_id": item_id, "status": "uploaded"}


@router.delete("/{item_id}")
async def delete_vault_item(item_id: str, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    item = supabase.table("vault_items").select("*").eq("id", item_id).eq("user_id", current_user["id"]).single().execute()
    
    if not item.data:
        raise HTTPException(status_code=404, detail="Vault item not found")
    
    try:
        delete_from_r2(item.data["r2_url"])
    except Exception as e:
        logger.warning(f"Failed to delete from R2: {e}")
    supabase.table("vault_items").delete().eq("id", item_id).execute()
    
    return {"message": "Vault item deleted"}


@router.post("/presets")
async def create_preset(
    name: str = Form(...),
    prompt: str = Form(...),
    quick_vibe: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    supabase = get_supabase()
    item_id = str(uuid4())
    
    import json
    preset_data = json.dumps({"prompt": prompt, "quick_vibe": quick_vibe})
    r2_key = f"vault/{current_user['id']}/preset/{item_id}.json"
    
    from services.r2 import upload_to_r2
    upload_to_r2(r2_key, preset_data.encode(), "application/json")
    
    supabase.table("vault_items").insert({
        "id": item_id,
        "user_id": current_user["id"],
        "type": "preset",
        "name": name,
        "r2_url": r2_key
    }).execute()
    
    return {"item_id": item_id, "name": name}