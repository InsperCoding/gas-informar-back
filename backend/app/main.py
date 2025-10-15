# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import users, aulas, uploads  # uploads adicionado
from . import models
from .database import engine
import os

app = FastAPI(title="GAS Informar - API")

# Configuração de CORS
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static/upload dir exists (para armazenar imagens)
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# monta static (serve /static/...)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Inclui os routers da aplicação (ordem não crítica)
app.include_router(users.router)
app.include_router(aulas.router)
app.include_router(uploads.router)  # router de uploads

@app.get("/")
def root():
    return {"msg": "API do GAS Informar rodando com sucesso!"}
