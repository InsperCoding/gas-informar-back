from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any

from .. import auth

router = APIRouter()

@router.post("/uploads", status_code=201)
async def upload_image(current_user: Any = Depends(auth.get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Upload de arquivos desativado neste ambiente (Vercel). Use storage externo."
    )