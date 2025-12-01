# routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import List, Optional

from .. import models, schemas, auth

router = APIRouter(
    prefix="/usuarios",
    tags=["Usuários"]
)

@router.post("/token", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(auth.get_db)):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Usuário ou senha incorretos")
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/", response_model=schemas.UserOut)
def register(user_data: schemas.UserCreate, db: Session = Depends(auth.get_db)):
    """
    Cria usuário. Se for uma criação pública (registro), mantenha as regras que desejar.
    user_data.turma será aplicada se fornecida (pode ser None).
    """
    if db.query(models.User).filter(models.User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username já cadastrado")

    hashed_password = auth.hash_password(user_data.senha)
    new_user = models.User(
        nome=user_data.nome,
        username=user_data.username,
        senha_hash=hashed_password,
        role=user_data.role,
        turma=getattr(user_data, "turma", None) if getattr(user_data, "turma", None) is not None else None,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/me", response_model=schemas.UserOut)
def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@router.get("/", response_model=List[schemas.UserOut])
def list_users(db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Apenas administradores podem listar todos os usuários")
    # opcional: order by id or nome
    return db.query(models.User).order_by(models.User.id.desc()).all()


@router.put("/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int,
    user_update: schemas.UserUpdate,
    db: Session = Depends(auth.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Admins podem atualizar qualquer usuário.
    Usuário pode atualizar seu próprio perfil também.
    Usa user_update.__fields_set__ para aplicar campos que vieram no payload (incluindo None).
    """
    # autorização: admin ou o próprio usuário
    if not (current_user.role == "admin" or current_user.id == user_id):
        raise HTTPException(status_code=403, detail="Permissão negada")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    fields_set = getattr(user_update, "__fields_set__", set())

    # nome
    if "nome" in fields_set:
        user.nome = user_update.nome

    # username (checa conflito)
    if "username" in fields_set and user_update.username is not None:
        existing = db.query(models.User).filter(models.User.username == user_update.username, models.User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username já cadastrado por outro usuário")
        user.username = user_update.username

    # role (só admin pode alterar role)
    if "role" in fields_set and user_update.role is not None:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Apenas administradores podem alterar a role")
        user.role = user_update.role
        # se a role deixar de ser 'aluno', limpamos turma por segurança
        if user.role != "aluno":
            user.turma = None

    # senha
    if "senha" in fields_set and user_update.senha:
        user.senha_hash = auth.hash_password(user_update.senha)

    # TURMA: aplicar se o campo foi enviado (mesmo que seja None -> limpar)
    if "turma" in fields_set:
        # somente faça sentido guardar turma em alunos; se role atual do user não for aluno, você pode optar por ignorar ou limpar
        if user_update.turma is None:
            user.turma = None
        else:
            user.turma = user_update.turma

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Apenas administradores podem deletar usuários")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    db.delete(user)
    db.commit()
    return None
