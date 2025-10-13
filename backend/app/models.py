from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.types import Enum as SQLEnum
from datetime import datetime
import enum

from .database import Base

# Tipo de exercício (apenas para clareza; armazenado como Enum no DB)
class ExerciseTypeEnum(str, enum.Enum):
    text = "text"
    multiple_choice = "multiple_choice"

# Usuário
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, index=True, nullable=False)
    role = Column(String(50), nullable=False, default="aluno")  # 'admin', 'professor', 'aluno'
    senha_hash = Column(String(300), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # relações simples (backrefs usados por outros modelos)
    aulas = relationship("Aula", back_populates="autor", cascade="all, delete-orphan")
    respostas = relationship("RespostaAluno", back_populates="aluno", cascade="all, delete-orphan")


class Aula(Base):
    __tablename__ = "aulas"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(200), nullable=False)
    descricao = Column(Text, nullable=True)
    autor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    autor = relationship("User", back_populates="aulas")
    blocos = relationship("ConteudoBloco", back_populates="aula", cascade="all, delete-orphan", order_by="ConteudoBloco.ordem")
    exercicios = relationship("Exercicio", back_populates="aula", cascade="all, delete-orphan", order_by="Exercicio.ordem")


class ConteudoBloco(Base):
    __tablename__ = "conteudo_blocos"
    id = Column(Integer, primary_key=True, index=True)
    aula_id = Column(Integer, ForeignKey("aulas.id", ondelete="CASCADE"))
    titulo = Column(String(200), nullable=True)
    texto = Column(Text, nullable=True)
    ordem = Column(Integer, default=0)  # para ordenar os blocos dentro da aula

    aula = relationship("Aula", back_populates="blocos")


class Exercicio(Base):
    __tablename__ = "exercicios"
    id = Column(Integer, primary_key=True, index=True)
    aula_id = Column(Integer, ForeignKey("aulas.id", ondelete="CASCADE"))
    titulo = Column(String(200), nullable=True)
    enunciado = Column(Text, nullable=False)
    tipo = Column(SQLEnum(ExerciseTypeEnum), nullable=False, default=ExerciseTypeEnum.text)
    resposta_modelo = Column(Text, nullable=True)  # para comparação simples em exercícios texto
    pontos = Column(Integer, default=1)
    ordem = Column(Integer, default=0)

    aula = relationship("Aula", back_populates="exercicios")
    alternativas = relationship("Alternativa", back_populates="exercicio", cascade="all, delete-orphan")
    respostas = relationship("RespostaAluno", back_populates="exercicio", cascade="all, delete-orphan")


class Alternativa(Base):
    __tablename__ = "alternativas"
    id = Column(Integer, primary_key=True, index=True)
    exercicio_id = Column(Integer, ForeignKey("exercicios.id", ondelete="CASCADE"))
    texto = Column(Text, nullable=False)
    is_correta = Column(Boolean, default=False)

    exercicio = relationship("Exercicio", back_populates="alternativas")


class RespostaAluno(Base):
    __tablename__ = "respostas_aluno"
    id = Column(Integer, primary_key=True, index=True)
    exercicio_id = Column(Integer, ForeignKey("exercicios.id", ondelete="CASCADE"))
    aluno_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    enviado_em = Column(DateTime, default=datetime.utcnow)
    resposta_texto = Column(Text, nullable=True)
    alternativa_id = Column(Integer, ForeignKey("alternativas.id"), nullable=True)
    pontuacao = Column(Integer, default=0)

    exercicio = relationship("Exercicio", back_populates="respostas")
    aluno = relationship("User", back_populates="respostas")
    alternativa = relationship("Alternativa")
