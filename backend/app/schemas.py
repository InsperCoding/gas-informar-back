from pydantic import BaseModel, EmailStr
from typing import Optional

class UserBase(BaseModel):
    nome: str
    email: EmailStr
    role: str

class UserCreate(UserBase):
    senha: str

class UserOut(UserBase):
    id: int
    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
