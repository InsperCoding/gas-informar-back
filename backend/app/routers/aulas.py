from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from .. import models, schemas, auth

router = APIRouter(prefix="/aulas", tags=["Aulas"])

# helper: checar role
def require_role(user: models.User, allowed_roles: List[str]):
    if user.role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão negada")

@router.get("/", response_model=List[schemas.AulaOut])
def listar_aulas(skip: int = 0, limit: int = 50, db: Session = Depends(auth.get_db)):
    aulas = db.query(models.Aula).offset(skip).limit(limit).all()
    return aulas

@router.get("/{aula_id}", response_model=schemas.AulaOut)
def obter_aula(aula_id: int, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    aula = db.query(models.Aula).filter(models.Aula.id == aula_id).first()
    if not aula:
        raise HTTPException(status_code=404, detail="Aula não encontrada")
    return aula

@router.post("/", response_model=schemas.AulaOut)
def criar_aula(payload: schemas.AulaCreate, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    require_role(current_user, ["admin", "professor"])
    aula = models.Aula(titulo=payload.titulo, descricao=payload.descricao, autor_id=current_user.id)
    db.add(aula)
    db.flush()  # garante que aula.id exista antes de criar blocos/exercicios

    # blocos (agora incluindo imagem_url se fornecido)
    for i, bloco in enumerate(payload.blocos or []):
        cb = models.ConteudoBloco(
            aula_id=aula.id,
            titulo=bloco.titulo,
            texto=bloco.texto,
            ordem=(bloco.ordem if bloco.ordem is not None else i),
            imagem_url=(getattr(bloco, "imagem_url", None) if getattr(bloco, "imagem_url", None) else None)
        )
        db.add(cb)

    # exercicios
    for i, ex in enumerate(payload.exercicios or []):
        # converter tipo do schema para o Enum do model
        tipo_model = models.ExerciseTypeEnum(ex.tipo.value)
        ex_model = models.Exercicio(
            aula_id=aula.id,
            titulo=ex.titulo,
            enunciado=ex.enunciado,
            tipo=tipo_model,
            resposta_modelo=ex.resposta_modelo,
            pontos=(ex.pontos or 1),
            ordem=(ex.ordem if ex.ordem is not None else i)
        )
        db.add(ex_model)
        db.flush()
        if ex.tipo == schemas.ExerciseType.multiple_choice and ex.alternativas:
            corretas = set(ex.alternativas_certas or [])
            for idx, texto_alt in enumerate(ex.alternativas):
                alt = models.Alternativa(
                    exercicio_id=ex_model.id,
                    texto=texto_alt,
                    is_correta=(idx in corretas)
                )
                db.add(alt)

    db.commit()
    db.refresh(aula)
    return aula

@router.put("/{aula_id}", response_model=schemas.AulaOut)
def atualizar_aula(aula_id: int, payload: schemas.AulaCreate, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    # apenas admin/professor
    require_role(current_user, ["admin", "professor"])
    aula = db.query(models.Aula).filter(models.Aula.id == aula_id).first()
    if not aula:
        raise HTTPException(status_code=404, detail="Aula não encontrada")

    # atualizar campos simples
    aula.titulo = payload.titulo
    aula.descricao = payload.descricao

    # --- SINCRONIZAÇÃO DE BLOCOS (update/create/delete) ---
    # obter blocos existentes do BD mapeados por id
    existing_blocos = {b.id: b for b in aula.blocos or []}

    incoming_blocos = payload.blocos or []

    # ids recebidos (para saber o que manter)
    incoming_ids = set()
    for idx, bloco_payload in enumerate(incoming_blocos):
        # bloco_payload pode ser pydantic model -> acessar com getattr
        bloco_id = getattr(bloco_payload, "id", None)
        imagem_url = getattr(bloco_payload, "imagem_url", None)

        if bloco_id and bloco_id in existing_blocos:
            # atualizar bloco existente
            b = existing_blocos[bloco_id]
            b.titulo = bloco_payload.titulo
            b.texto = bloco_payload.texto
            b.ordem = bloco_payload.ordem if bloco_payload.ordem is not None else idx
            b.imagem_url = imagem_url if imagem_url else None
            incoming_ids.add(bloco_id)
        else:
            # criar novo bloco
            cb = models.ConteudoBloco(
                aula_id=aula.id,
                titulo=bloco_payload.titulo,
                texto=bloco_payload.texto,
                ordem=(bloco_payload.ordem if bloco_payload.ordem is not None else idx),
                imagem_url=(imagem_url if imagem_url else None)
            )
            db.add(cb)
            # NOTE: não adicionamos id em incoming_ids porque ainda não tem id no DB

    # deletar blocos que existem no DB mas não vieram no payload
    for existing_id, existing_obj in list(existing_blocos.items()):
        if existing_id not in incoming_ids:
            db.delete(existing_obj)

    # --- RECRIAÇÃO / SINCRONIZAÇÃO DE EXERCICIOS (mantive seu fluxo atual) ---
    # remover todos os exercícios antigos (seguindo sua estratégia anterior)
    for exo in list(aula.exercicios):
        db.delete(exo)
    db.flush()

    # recriar exercicios + alternativas (a lógica permanece igual)
    for i, ex in enumerate(payload.exercicios or []):
        tipo_model = models.ExerciseTypeEnum(ex.tipo.value)
        ex_model = models.Exercicio(
            aula_id=aula.id,
            titulo=ex.titulo,
            enunciado=ex.enunciado,
            tipo=tipo_model,
            resposta_modelo=ex.resposta_modelo,
            pontos=(ex.pontos or 1),
            ordem=(ex.ordem if ex.ordem is not None else i)
        )
        db.add(ex_model)
        db.flush()
        if ex.tipo == schemas.ExerciseType.multiple_choice and ex.alternativas:
            corretas = set(ex.alternativas_certas or [])
            for idx, texto_alt in enumerate(ex.alternativas):
                alt = models.Alternativa(
                    exercicio_id=ex_model.id,
                    texto=texto_alt,
                    is_correta=(idx in corretas)
                )
                db.add(alt)

    db.commit()
    db.refresh(aula)
    return aula

@router.delete("/{aula_id}")
def deletar_aula(aula_id: int, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    require_role(current_user, ["admin"])
    aula = db.query(models.Aula).filter(models.Aula.id == aula_id).first()
    if not aula:
        raise HTTPException(status_code=404, detail="Aula não encontrada")
    db.delete(aula)
    db.commit()
    return {"detail": "Aula deletada"}

@router.post("/{aula_id}/exercicios", response_model=schemas.ExercicioOut)
def criar_exercicio(aula_id: int, payload: schemas.ExercicioCreate, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    require_role(current_user, ["admin", "professor"])
    aula = db.query(models.Aula).filter(models.Aula.id == aula_id).first()
    if not aula:
        raise HTTPException(status_code=404, detail="Aula não encontrada")

    tipo_model = models.ExerciseTypeEnum(payload.tipo.value)
    ex_model = models.Exercicio(
        aula_id=aula.id,
        titulo=payload.titulo,
        enunciado=payload.enunciado,
        tipo=tipo_model,
        resposta_modelo=payload.resposta_modelo,
        pontos=(payload.pontos or 1),
        ordem=(payload.ordem or 0)
    )
    db.add(ex_model)
    db.flush()

    if payload.tipo == schemas.ExerciseType.multiple_choice and payload.alternativas:
        corretas = set(payload.alternativas_certas or [])
        for idx, texto_alt in enumerate(payload.alternativas):
            alt = models.Alternativa(
                exercicio_id=ex_model.id,
                texto=texto_alt,
                is_correta=(idx in corretas)
            )
            db.add(alt)

    db.commit()
    db.refresh(ex_model)
    return ex_model

@router.post("/responder", response_model=schemas.RespostaOut)
def submeter_resposta(payload: schemas.RespostaCreate, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    # alunos (e também admin/prof podem submeter para testes)
    require_role(current_user, ["aluno", "professor", "admin"])
    exercicio = db.query(models.Exercicio).filter(models.Exercicio.id == payload.exercicio_id).first()
    if not exercicio:
        raise HTTPException(status_code=404, detail="Exercício não encontrado")

    pontuacao = 0
    # múltipla escolha
    if exercicio.tipo == models.ExerciseTypeEnum.multiple_choice:
        if payload.alternativa_id is None:
            raise HTTPException(status_code=400, detail="alternativa_id é obrigatória para múltipla escolha")
        alternativa_model = db.query(models.Alternativa).filter(
            models.Alternativa.id == payload.alternativa_id,
            models.Alternativa.exercicio_id == exercicio.id
        ).first()
        if not alternativa_model:
            raise HTTPException(status_code=404, detail="Alternativa não encontrada")
        if alternativa_model.is_correta:
            pontuacao = exercicio.pontos
    else:
        # texto: comparação simples com resposta_modelo (se existir)
        if exercicio.resposta_modelo and payload.resposta_texto:
            if exercicio.resposta_modelo.strip().lower() == payload.resposta_texto.strip().lower():
                pontuacao = exercicio.pontos
        # caso não haja resposta_modelo, pontuação fica 0 (pode ser corrigido manualmente posteriormente)

    resposta = models.RespostaAluno(
        exercicio_id=exercicio.id,
        aluno_id=current_user.id,
        resposta_texto=payload.resposta_texto,
        alternativa_id=payload.alternativa_id,
        pontuacao=pontuacao
    )
    db.add(resposta)
    db.commit()
    db.refresh(resposta)
    return resposta

@router.get("/desempenho/{aluno_id}", response_model=List[schemas.RespostaOut])
def ver_desempenho(aluno_id: int, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    require_role(current_user, ["admin", "professor"])
    respostas = db.query(models.RespostaAluno).filter(models.RespostaAluno.aluno_id == aluno_id).all()
    return respostas
