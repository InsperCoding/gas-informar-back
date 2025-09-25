from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    senha_hash = Column(Text, nullable=False)
    role = Column(String(20), nullable=False)
    criado_em = Column(TIMESTAMP, server_default=func.now())

    aulas = relationship("Aula", back_populates="professor")

class Aula(Base):
    __tablename__ = "aulas"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(200), nullable=False)
    descricao = Column(Text)
    professor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    criado_em = Column(TIMESTAMP, server_default=func.now())

    professor = relationship("User", back_populates="aulas")
    conteudos = relationship("Conteudo", back_populates="aula")
    exercicios = relationship("Exercicio", back_populates="aula")

class Conteudo(Base):
    __tablename__ = "conteudos"
    id = Column(Integer, primary_key=True, index=True)
    aula_id = Column(Integer, ForeignKey("aulas.id", ondelete="CASCADE"))
    tipo = Column(String(20), nullable=False)
    titulo = Column(String(200))
    conteudo = Column(Text)
    ordem = Column(Integer, nullable=False)
    criado_em = Column(TIMESTAMP, server_default=func.now())

    aula = relationship("Aula", back_populates="conteudos")

class Exercicio(Base):
    __tablename__ = "exercicios"
    id = Column(Integer, primary_key=True, index=True)
    aula_id = Column(Integer, ForeignKey("aulas.id", ondelete="CASCADE"))
    tipo = Column(String(30), nullable=False)
    pergunta = Column(Text, nullable=False)
    resposta_correta = Column(Text)
    criado_em = Column(TIMESTAMP, server_default=func.now())

    aula = relationship("Aula", back_populates="exercicios")
    opcoes = relationship("OpcaoExercicio", back_populates="exercicio")

class OpcaoExercicio(Base):
    __tablename__ = "opcoes_exercicios"
    id = Column(Integer, primary_key=True, index=True)
    exercicio_id = Column(Integer, ForeignKey("exercicios.id", ondelete="CASCADE"))
    texto = Column(Text, nullable=False)

    exercicio = relationship("Exercicio", back_populates="opcoes")

class RespostaAluno(Base):
    __tablename__ = "respostas_alunos"
    id = Column(Integer, primary_key=True, index=True)
    exercicio_id = Column(Integer, ForeignKey("exercicios.id", ondelete="CASCADE"))
    aluno_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    resposta = Column(Text, nullable=False)
    correta = Column(Boolean)
    enviado_em = Column(TIMESTAMP, server_default=func.now())
