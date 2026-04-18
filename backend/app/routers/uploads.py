import os
import uuid
from typing import Any

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi import status
from supabase import create_client, Client

from .. import auth

router = APIRouter()

ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "uploads")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    supabase: Client | None = None
else:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


@router.post("/uploads", status_code=201)
async def upload_image(
    file: UploadFile = File(...),
    current_user: Any = Depends(auth.get_current_user),
):
    if supabase is None:
        raise HTTPException(
            status_code=500,
            detail="Supabase Storage não configurado no servidor.",
        )

    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Tipo de arquivo não permitido")

    contents = await file.read()
    if len(contents) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (max 5MB)")

    new_name = f"{uuid.uuid4().hex}.{ext}"
    path = f"images/{new_name}"

    try:
        supabase.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
            path,
            contents,
            {"content-type": file.content_type or "application/octet-stream"}
        )

        public_url = supabase.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(path)

        return {
            "url": public_url,
            "path": path,
            "bucket": SUPABASE_STORAGE_BUCKET,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao enviar arquivo para o storage: {str(e)}"
        )