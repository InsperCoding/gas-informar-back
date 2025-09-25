from fastapi import FastAPI
from . import models
from .database import engine

app = FastAPI()

# Create the database tables if they do not exist
models.Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"msg": "API rodando"}
