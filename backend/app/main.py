from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import users, aulas  # import dos routers
from . import models
from .database import engine

app = FastAPI(title="GAS Informar - API")

# Configuração de CORS
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",  # caso de Vite
    "http://127.0.0.1:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Importante:
# O banco deve ser criado/resetado com: python scripts/reset_db.py

# Inclui os routers da aplicação
app.include_router(users.router)
app.include_router(aulas.router)

@app.get("/")
def root():
    return {"msg": "API do GAS Informar rodando com sucesso 🚀"}
