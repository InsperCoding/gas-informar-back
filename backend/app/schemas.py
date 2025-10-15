from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum

# ---------- usuários ----------
class UserBase(BaseModel):
    nome: str
    email: EmailStr
    role: str  # 'admin' | 'professor' | 'aluno'

class UserCreate(UserBase):
    senha: str

class UserOut(UserBase):
    id: int
    class Config:
        orm_mode = True

class UserUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None  # 'admin' | 'professor' | 'aluno'
    senha: Optional[str] = None

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None


# ---------- aulas / conteúdo / exercícios ----------
class ConteudoBlocoCreate(BaseModel):
    titulo: Optional[str] = None
    texto: Optional[str] = None
    ordem: Optional[int] = 0

class ConteudoBlocoOut(ConteudoBlocoCreate):
    id: int
    class Config:
        orm_mode = True

class ExerciseType(str, Enum):
    text = "text"
    multiple_choice = "multiple_choice"

class ExercicioCreate(BaseModel):
    titulo: Optional[str] = None
    enunciado: str
    tipo: ExerciseType
    resposta_modelo: Optional[str] = None
    pontos: Optional[int] = 1
    ordem: Optional[int] = 0
    alternativas: Optional[List[str]] = None  # apenas textos das alternativas
    alternativas_certas: Optional[List[int]] = None  # índices (0-based) das corretas

class AlternativaOut(BaseModel):
    id: int
    texto: str
    class Config:
        orm_mode = True

class ExercicioOut(BaseModel):
    id: int
    titulo: Optional[str] = None
    enunciado: str
    tipo: ExerciseType
    pontos: int
    alternativas: Optional[List[AlternativaOut]] = []
    class Config:
        orm_mode = True

class AulaCreate(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    blocos: Optional[List[ConteudoBlocoCreate]] = []
    exercicios: Optional[List[ExercicioCreate]] = []

class AulaOut(BaseModel):
    id: int
    titulo: str
    descricao: Optional[str]
    autor_id: int
    blocos: List[ConteudoBlocoOut] = []
    exercicios: List[ExercicioOut] = []
    created_at: datetime
    class Config:
        orm_mode = True


# ---------- respostas ----------
class RespostaCreate(BaseModel):
    exercicio_id: int
    resposta_texto: Optional[str] = None
    alternativa_id: Optional[int] = None

class RespostaOut(BaseModel):
    id: int
    exercicio_id: int
    aluno_id: int
    enviado_em: datetime
    resposta_texto: Optional[str]
    alternativa_id: Optional[int]
    pontuacao: int
    class Config:
        orm_mode = True
