import os
import uuid
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi import status
from typing import Any

from .. import auth

router = APIRouter()

UPLOAD_DIR = "static/uploads"
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB

os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/uploads", status_code=201)
async def upload_image(file: UploadFile = File(...), current_user: Any = Depends(auth.get_current_user)):
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
    dest_path = os.path.join(UPLOAD_DIR, new_name)

    with open(dest_path, "wb") as f:
        f.write(contents)

    url = f"/static/uploads/{new_name}"
    return {"url": url}
