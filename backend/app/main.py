from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from .routers import users
from . import models
from .database import engine

app = FastAPI()

# CORS settings
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create the database tables if they do not exist
models.Base.metadata.create_all(bind=engine)

# Include routers
app.include_router(users.router)

@app.get("/")
def root():
    return {"msg": "API rodando"}
