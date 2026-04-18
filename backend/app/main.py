from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import users, aulas, uploads
from . import models
from .database import engine

app = FastAPI(title="GAS Informar - API")

# CORS
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://gas-informar-front.vercel.app",
    "https://informar.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(users.router)
app.include_router(aulas.router)
app.include_router(uploads.router)

# Health check
@app.get("/")
def root():
    return {"msg": "API do GAS Informar rodando com sucesso!"}