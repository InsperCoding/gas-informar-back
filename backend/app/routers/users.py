# routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import List

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
        data={"sub": user.email, "role": user.role},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/", response_model=schemas.UserOut)
def register(user_data: schemas.UserCreate, db: Session = Depends(auth.get_db)):
    if db.query(models.User).filter(models.User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    hashed_password = auth.hash_password(user_data.senha)
    new_user = models.User(
        nome=user_data.nome,
        email=user_data.email,
        senha_hash=hashed_password,
        role=user_data.role
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
    return db.query(models.User).all()

@router.put("/{user_id}", response_model=schemas.UserOut)
def update_user(user_id: int, user_update: schemas.UserUpdate, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    # somente admin pode atualizar outros usuários
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Apenas administradores podem atualizar usuários")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # atualiza campos se presentes
    if user_update.nome is not None:
        user.nome = user_update.nome
    if user_update.email is not None:
        # checa conflito de email com outro usuário
        existing = db.query(models.User).filter(models.User.email == user_update.email, models.User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email já cadastrado por outro usuário")
        user.email = user_update.email
    if user_update.role is not None:
        user.role = user_update.role
    if user_update.senha is not None and user_update.senha != "":
        user.senha_hash = auth.hash_password(user_update.senha)

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
