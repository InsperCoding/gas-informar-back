# aulas.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime
import re
import json

from .. import models, schemas, auth

router = APIRouter(prefix="/aulas", tags=["Aulas"])

# helper: checar role
def require_role(user: models.User, allowed_roles: List[str]):
    if user.role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão negada")

# Regex para detectar padrões antigos como:
# id=1 texto='algum texto' is_correta=False
# id=1 texto="algum texto" is_correta=True
_PAT_ALTERNATIVA = re.compile(
    r"id=(?P<id>[^ ]+)\s+texto=(?:'(?P<t1>[^']*)'|\"(?P<t2>[^\"]*)\")\s+is_correta=(?P<is>True|False)",
    re.IGNORECASE,
)

def extract_innermost(text: str):
    """
    Tenta extrair recursivamente o 'texto' e 'is_correta' de strings que contenham
    a serialização antiga. Retorna (clean_text, is_correta_bool_or_None, found_flag).
    Se nada for encontrado, devolve (original_text, None, False).
    """
    if not isinstance(text, str):
        return text, None, False

    cur = text
    extracted_is = None
    found_any = False

    # Limitamos a iterações para evitar loops infinitos
    for _ in range(6):
        m = _PAT_ALTERNATIVA.search(cur)
        if not m:
            break
        inner = m.group("t1") if m.group("t1") is not None else m.group("t2")
        raw_is = m.group("is")
        # prepare for next loop: inner might itself contain the pattern
        cur = inner
        extracted_is = True if raw_is.lower() == "true" else False
        found_any = True

    return cur, (extracted_is if extracted_is is not None else None), found_any

# helper: normaliza alternativas (payload) -> lista de objetos com id/texto/is_correta
def normalize_alternativas_payload(incoming_alternativas, incoming_certas_indices=None):
    """
    incoming_alternativas: list of dicts or strings
    incoming_certas_indices: iterable de índices (opcional)
    Returns: (alternativas_list, correct_ids)
      - alternativas_list: [{id:int, texto:str, is_correta:bool}, ...]
      - correct_ids: list of ids (ints)
    Também limpa automaticamente textos que contenham serializações antigas.
    """
    incoming_certas_indices = set(incoming_certas_indices or [])
    normalized = []
    next_id = 1

    for ai, alt_item in enumerate(incoming_alternativas or []):
        # padrão do alt após normalização
        texto = ""
        aid = None
        is_corr = None

        if isinstance(alt_item, dict):
            # pegar campos básicos
            texto_raw = alt_item.get("texto", "") or ""
            provided_id = alt_item.get("id")
            is_corr_field = alt_item.get("is_correta", None)

            # tentar extrair texto limpo se texto_raw estiver sujo
            cleaned_text, extracted_is, found = extract_innermost(texto_raw)

            if found:
                texto = cleaned_text
                # se o payload não trouxe is_correta, use o valor extraído
                is_corr = extracted_is if is_corr_field is None else bool(is_corr_field)
            else:
                texto = texto_raw
                is_corr = bool(is_corr_field) if is_corr_field is not None else (ai in incoming_certas_indices)

            if provided_id is None:
                # se não forneceu id, vamos atribuir um id local sequencial
                aid = next_id
                next_id += 1
            else:
                try:
                    aid = int(provided_id)
                except Exception:
                    # se o id fornecido não for int, ignora e gera um
                    aid = next_id
                    next_id += 1
                next_id = max(next_id, aid + 1)

        else:
            # alt_item pode ser string (antigo) ou outro tipo; tentamos extrair
            texto_raw = str(alt_item or "")
            cleaned_text, extracted_is, found = extract_innermost(texto_raw)
            if found:
                texto = cleaned_text
                is_corr = extracted_is if extracted_is is not None else (ai in incoming_certas_indices)
            else:
                texto = texto_raw
                is_corr = (ai in incoming_certas_indices)

            aid = next_id
            next_id += 1

        normalized.append({"id": aid, "texto": texto, "is_correta": bool(is_corr)})

    # recomputa lista de ids corretos
    correct_ids = [a["id"] for a in normalized if a.get("is_correta")]
    return normalized, correct_ids

# -----------------------
# POST /aulas/{aula_id}/finalizar
# -----------------------
@router.post("/{aula_id}/finalizar")
def finalizar_tentativa(aula_id: int, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    # qualquer aluno pode finalizar sua tentativa; professores/admins podem finalizar para teste
    aula = db.query(models.Aula).filter(models.Aula.id == aula_id).first()
    if not aula:
        raise HTTPException(status_code=404, detail="Aula não encontrada")

    # buscar respostas do aluno para exercícios dessa aula
    respostas = (
        db.query(models.RespostaAluno)
        .join(models.Exercicio, models.RespostaAluno.exercicio_id == models.Exercicio.id)
        .filter(models.Exercicio.aula_id == aula_id, models.RespostaAluno.aluno_id == current_user.id)
        .all()
    )

    total = sum((r.pontuacao or 0) for r in respostas)

    # procurar tentativa existente NÃO finalizada (se houver) ou criar nova
    tentativa = (
        db.query(models.TentativaAula)
        .filter(
            models.TentativaAula.aula_id == aula_id,
            models.TentativaAula.aluno_id == current_user.id,
            models.TentativaAula.finalizada == False,  # apenas não-finalizadas
        )
        .order_by(models.TentativaAula.created_at.desc())
        .first()
    )

    if not tentativa:
        # cria nova tentativa já finalizada
        tentativa = models.TentativaAula(
            aluno_id=current_user.id,
            aula_id=aula_id,
            finalizada=True,
            pontuacao=total,
            created_at=datetime.utcnow(),
            finalized_at=datetime.utcnow(),
        )
        db.add(tentativa)
        db.flush()  # garante tente.id antes de vincular respostas abaixo
    else:
        # atualiza tentativa não-finalizada para finalizada
        tentativa.finalizada = True
        tentativa.pontuacao = total
        tentativa.finalized_at = datetime.utcnow()

    # linkar respostas à tentativa (apenas as que não têm tentativa_id)
    for r in respostas:
        if r.tentativa_id is None:
            r.tentativa_id = tentativa.id

    db.commit()
    return {"status": "finalizada", "pontuacao": total}

# -----------------------
# GET /aulas/{aula_id}/desempenho/{aluno_id}
# -----------------------
@router.get("/{aula_id}/desempenho/{aluno_id}")
def desempenho_aula_por_aluno(aula_id: int, aluno_id: int, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    # professores/admins podem ver de qualquer aluno; aluno só pode ver o próprio
    if current_user.role not in ("admin", "professor") and current_user.id != aluno_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão negada")

    aula = db.query(models.Aula).options(joinedload(models.Aula.exercicios)).filter(models.Aula.id == aula_id).first()
    if not aula:
        raise HTTPException(status_code=404, detail="Aula não encontrada")

    tentativa = (
        db.query(models.TentativaAula)
        .filter(models.TentativaAula.aula_id == aula_id, models.TentativaAula.aluno_id == aluno_id)
        .order_by(models.TentativaAula.created_at.desc())
        .first()
    )

    respostas = (
        db.query(models.RespostaAluno)
        .join(models.Exercicio, models.RespostaAluno.exercicio_id == models.Exercicio.id)
        .filter(models.Exercicio.aula_id == aula_id, models.RespostaAluno.aluno_id == aluno_id)
        .all()
    )

    resp_map = {r.exercicio_id: r for r in respostas}

    results = []
    total_obtido = 0

    for ex in aula.exercicios or []:
        r = resp_map.get(ex.id)
        item = {
            "exercicio_id": ex.id,
            "enunciado": ex.enunciado,
            "resposta_aluno": r.resposta_texto if r else None,
            "alternativa_escolhida_id": r.alternativa_id if r else None,
            "acertou": ((r.pontuacao or 0) > 0) if r else False,
            "pontuacao_obtida": r.pontuacao if r else 0,
            "resposta_modelo": ex.resposta_modelo,
            "feedback_professor": r.feedback_professor if r else None,
        }
        total_obtido += (r.pontuacao or 0) if r else 0
        results.append(item)

    response = {
        "aula_id": aula_id,
        "aluno_id": aluno_id,
        "pontuacao_total": tentativa.pontuacao if (tentativa and tentativa.pontuacao is not None) else total_obtido,
        "finalizada": bool(tentativa.finalizada) if tentativa else False,
        "responses": results,
    }

    return response

@router.post("/respostas/{resposta_id}/feedback")
def gravar_feedback_resposta(resposta_id: int, payload: dict, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    require_role(current_user, ["admin", "professor"])

    resposta = db.query(models.RespostaAluno).filter(models.RespostaAluno.id == resposta_id).first()
    if not resposta:
        raise HTTPException(status_code=404, detail="Resposta não encontrada")

    feedback = payload.get("feedback") or None
    resposta.feedback_professor = feedback
    db.commit()
    db.refresh(resposta)
    return {"status": "ok", "resposta_id": resposta.id, "feedback": resposta.feedback_professor}

@router.get("/", response_model=List[schemas.AulaOut])
def listar_aulas(skip: int = 0, limit: int = 50, db: Session = Depends(auth.get_db)):
    aulas = db.query(models.Aula).options(joinedload(models.Aula.blocos), joinedload(models.Aula.exercicios)).offset(skip).limit(limit).all()
    return aulas

@router.get("/{aula_id}", response_model=schemas.AulaOut)
def obter_aula(aula_id: int, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    aula = db.query(models.Aula).options(joinedload(models.Aula.blocos), joinedload(models.Aula.exercicios)).filter(models.Aula.id == aula_id).first()
    if not aula:
        raise HTTPException(status_code=404, detail="Aula não encontrada")
    return aula

# -----------------------
# criar aula (cria blocos/exercícios mas grava alternativas em JSONB)
# -----------------------
@router.post("/", response_model=schemas.AulaOut)
def criar_aula(payload: schemas.AulaCreate, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    require_role(current_user, ["admin", "professor"])
    aula = models.Aula(titulo=payload.titulo, descricao=payload.descricao, autor_id=current_user.id)
    db.add(aula)
    db.flush()  # garante aula.id

    # blocos (igual)
    for i, bloco in enumerate(payload.blocos or []):
        cb = models.ConteudoBloco(
            aula_id=aula.id,
            titulo=bloco.titulo,
            texto=bloco.texto,
            ordem=(bloco.ordem if bloco.ordem is not None else i),
            imagem_url=(getattr(bloco, "imagem_url", None) if getattr(bloco, "imagem_url", None) else None)
        )
        db.add(cb)

    # exercicios -> armazenar alternativas como JSONB
    for i, ex in enumerate(payload.exercicios or []):
        try:
            tipo_model = models.ExerciseTypeEnum(ex.tipo)
        except Exception:
            tipo_model = models.ExerciseTypeEnum.text

        ex_model = models.Exercicio(
            aula_id=aula.id,
            titulo=ex.titulo,
            enunciado=ex.enunciado,
            tipo=tipo_model,
            resposta_modelo=ex.resposta_modelo,
            pontos=(ex.pontos or 1),
            ordem=(ex.ordem if ex.ordem is not None else i)
        )
        incoming_alts = getattr(ex, "alternativas", []) or []
        incoming_certas_indices = set(getattr(ex, "alternativas_certas", []) or [])
        normalized_alts, correct_ids = normalize_alternativas_payload(incoming_alts, incoming_certas_indices)

        ex_model.alternativas = normalized_alts or []
        ex_model.correct_alternativas = correct_ids or []

        db.add(ex_model)

    db.commit()
    db.refresh(aula)
    return aula

# -----------------------
# PATCH /aulas/{aula_id} - sincroniza blocos/exercícios/alternativas por id
# -----------------------
@router.patch("/{aula_id}", response_model=schemas.AulaOut)
def atualizar_aula(aula_id: int, payload: schemas.AulaUpdate, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    require_role(current_user, ["admin", "professor"])
    aula = db.query(models.Aula).options(joinedload(models.Aula.exercicios), joinedload(models.Aula.blocos)).filter(models.Aula.id == aula_id).first()
    if not aula:
        raise HTTPException(status_code=404, detail="Aula não encontrada")

    # Atualiza campos simples apenas se vieram no payload
    if payload.titulo is not None:
        aula.titulo = payload.titulo
    if payload.descricao is not None:
        aula.descricao = payload.descricao

    # BLOCOS
    if payload.blocos is not None:
        existing_blocos = {b.id: b for b in (aula.blocos or [])}
        incoming_blocos = payload.blocos or []
        incoming_ids = set()
        for idx, bloco_payload in enumerate(incoming_blocos):
            bloco_id = getattr(bloco_payload, "id", None)
            ordem = bloco_payload.ordem if bloco_payload.ordem is not None else idx
            if bloco_id and bloco_id in existing_blocos:
                b = existing_blocos[bloco_id]
                b.titulo = bloco_payload.titulo
                b.texto = bloco_payload.texto
                b.ordem = ordem
                b.imagem_url = getattr(bloco_payload, "imagem_url", None) or None
                incoming_ids.add(bloco_id)
            else:
                novo = models.ConteudoBloco(
                    aula_id=aula.id,
                    titulo=bloco_payload.titulo,
                    texto=bloco_payload.texto,
                    ordem=ordem,
                    imagem_url=getattr(bloco_payload, "imagem_url", None) or None
                )
                db.add(novo)
        # deletar blocos que não vieram no payload
        for existing_id, existing_obj in list(existing_blocos.items()):
            if existing_id not in incoming_ids:
                db.delete(existing_obj)

    # EXERCÍCIOS (sincroniza por id) -> agora operamos com JSONB alternatives
    if payload.exercicios is not None:
        incoming_exs = payload.exercicios or []
        existing_exs = {ex.id: ex for ex in (aula.exercicios or [])}
        incoming_ex_ids = set()

        for idx, ex_payload in enumerate(incoming_exs):
            ordem = ex_payload.ordem if ex_payload.ordem is not None else idx
            pontos = ex_payload.pontos if ex_payload.pontos is not None else 1
            ex_id = getattr(ex_payload, "id", None)

            if ex_id and ex_id in existing_exs:
                # UPDATE existing exercise
                ex_model = existing_exs[ex_id]
                ex_model.titulo = ex_payload.titulo
                ex_model.enunciado = ex_payload.enunciado
                try:
                    ex_model.tipo = models.ExerciseTypeEnum(ex_payload.tipo)
                except Exception:
                    pass
                ex_model.resposta_modelo = ex_payload.resposta_modelo
                ex_model.pontos = pontos
                ex_model.ordem = ordem
                incoming_ex_ids.add(ex_id)

                # sincronizar alternativas: payload pode conter objetos ou strings
                incoming_alternativas = getattr(ex_payload, "alternativas", []) or []
                incoming_alternativas_certas = set(getattr(ex_payload, "alternativas_certas", []) or [])
                normalized_alts, correct_ids = normalize_alternativas_payload(incoming_alternativas, incoming_alternativas_certas)

                ex_model.alternativas = normalized_alts or []
                ex_model.correct_alternativas = correct_ids or []

            else:
                # CREATE new exercise
                try:
                    tipo_model = models.ExerciseTypeEnum(ex_payload.tipo)
                except Exception:
                    tipo_model = models.ExerciseTypeEnum.text

                ex_model = models.Exercicio(
                    aula_id=aula.id,
                    titulo=ex_payload.titulo,
                    enunciado=ex_payload.enunciado,
                    tipo=tipo_model,
                    resposta_modelo=ex_payload.resposta_modelo,
                    pontos=pontos,
                    ordem=ordem
                )
                incoming_alternativas = getattr(ex_payload, "alternativas", []) or []
                incoming_alternativas_certas = set(getattr(ex_payload, "alternativas_certas", []) or [])
                normalized_alts, correct_ids = normalize_alternativas_payload(incoming_alternativas, incoming_alternativas_certas)
                ex_model.alternativas = normalized_alts or []
                ex_model.correct_alternativas = correct_ids or []
                db.add(ex_model)
                db.flush()
                incoming_ex_ids.add(ex_model.id)

        # deletar exercícios que não vieram no payload
        for existing_id, existing_obj in list(existing_exs.items()):
            if existing_id not in incoming_ex_ids:
                db.delete(existing_obj)

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

# -----------------------
# POST /aulas/{aula_id}/exercicios  (criar único exercício)
# -----------------------
@router.post("/{aula_id}/exercicios", response_model=schemas.ExercicioOut)
def criar_exercicio(aula_id: int, payload: schemas.ExercicioCreate, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    require_role(current_user, ["admin", "professor"])
    aula = db.query(models.Aula).filter(models.Aula.id == aula_id).first()
    if not aula:
        raise HTTPException(status_code=404, detail="Aula não encontrada")

    try:
        tipo_model = models.ExerciseTypeEnum(payload.tipo)
    except Exception:
        tipo_model = models.ExerciseTypeEnum.text

    ex_model = models.Exercicio(
        aula_id=aula.id,
        titulo=payload.titulo,
        enunciado=payload.enunciado,
        tipo=tipo_model,
        resposta_modelo=payload.resposta_modelo,
        pontos=(payload.pontos or 1),
        ordem=(payload.ordem or 0)
    )

    incoming_alternativas = getattr(payload, "alternativas", []) or []
    incoming_alternativas_certas = set(getattr(payload, "alternativas_certas", []) or [])
    normalized_alts, correct_ids = normalize_alternativas_payload(incoming_alternativas, incoming_alternativas_certas)

    ex_model.alternativas = normalized_alts or []
    ex_model.correct_alternativas = correct_ids or []

    db.add(ex_model)
    db.commit()
    db.refresh(ex_model)
    return ex_model

# -----------------------
# submeter resposta (ajustada para JSONB alternativas)
# -----------------------
@router.post("/responder", response_model=schemas.RespostaOut)
def submeter_resposta(payload: schemas.RespostaCreate, db: Session = Depends(auth.get_db), current_user: models.User = Depends(auth.get_current_user)):
    require_role(current_user, ["aluno", "professor", "admin"])
    exercicio = db.query(models.Exercicio).filter(models.Exercicio.id == payload.exercicio_id).first()
    if not exercicio:
        raise HTTPException(status_code=404, detail="Exercício não encontrado")

    pontuacao = 0

    if payload.alternativa_id is not None:
        # valida alternativa_id dentro do JSONB alternativas
        alts = exercicio.alternativas or []
        # procura alternativa com esse id
        try:
            alvo_id = int(payload.alternativa_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Alternativa inválida")
        found = next((a for a in alts if int(a.get("id")) == alvo_id), None)
        if not found:
            raise HTTPException(status_code=400, detail="Alternativa inválida para este exercício")

        # checar se correta usando exercicio.correct_alternativas (lista de ids)
        correct_ids_raw = exercicio.correct_alternativas or []
        correct_ids = [int(x) for x in (correct_ids_raw or [])]
        if alvo_id in correct_ids:
            pontuacao = exercicio.pontos or 0
    else:
        # texto: comparação simples com resposta_modelo (se existir)
        if exercicio.resposta_modelo and payload.resposta_texto:
            if exercicio.resposta_modelo.strip().lower() == payload.resposta_texto.strip().lower():
                pontuacao = exercicio.pontos or 0

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
