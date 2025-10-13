"""
backend/scripts/create_admin.py

Cria ou atualiza um usuário admin no banco.
Uso:
  python scripts/create_admin.py --email admin@example.com
  python scripts/create_admin.py --email admin@example.com --name "Admin" --force
  GAS_ADMIN_EMAIL=admin@example.com GAS_ADMIN_PASSWORD=secret python scripts/create_admin.py

Observações:
- Execute a partir da pasta `backend/` para facilitar imports.
- Este script adiciona o diretório `backend/` ao sys.path para garantir que `app` seja importável.
"""

import os
import sys
import argparse
from getpass import getpass
from pathlib import Path

# Garantir que backend/ esteja no sys.path para permitir 'from app ...'
sys.path.append(str(Path(__file__).resolve().parent.parent))

# imports do projeto (assume que app/ é importável)
from app.database import SessionLocal
from app import models, auth

def confirm_double(prompt: str) -> bool:
    """
    Confirmação dupla com as mesmas strings que você usou:
    primeiro 'yes', e caso não, pede 'secondyes'.
    """
    ans = input(prompt + " Digite 'yes' para confirmar: ").strip()
    if ans.lower() == "yes":
        return True
    second = input("Digite 'secondyes' para confirmar definitivamente: ").strip()
    return second.lower() == "secondyes"

def create_or_update_admin(db, name: str, email: str, password: str, force: bool = False):
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        if not force:
            print(f"Usuário com email {email} já existe. Use --force para atualizar/sobrescrever.")
            return False
        # atualizar
        print(f"Atualizando usuário existente {email} para role=admin...")
        existing.nome = name
        existing.role = "admin"
        existing.senha_hash = auth.hash_password(password)
        db.add(existing)
        db.commit()
        print("Admin atualizado com sucesso.")
        return True
    else:
        # criar novo
        print(f"Criando novo admin {email} ...")
        new_user = models.User(
            nome=name,
            email=email,
            role="admin",
            senha_hash=auth.hash_password(password)
        )
        db.add(new_user)
        db.commit()
        print("Admin criado com sucesso.")
        return True

def main():
    parser = argparse.ArgumentParser(description="Criar/Atualizar admin no banco (scripts/create_admin.py)")
    parser.add_argument("--name", "-n", help="Nome do admin", default=os.getenv("GAS_ADMIN_NAME", "Admin"))
    parser.add_argument("--email", "-e", help="Email do admin", default=os.getenv("GAS_ADMIN_EMAIL"))
    parser.add_argument("--password", "-p", help="Senha do admin (não recomendado passar por CLI)", default=os.getenv("GAS_ADMIN_PASSWORD"))
    parser.add_argument("--force", "-f", action="store_true", help="Se o usuário existir, atualizar/sobrescrever")
    parser.add_argument("--yes", action="store_true", help="Pular confirmação interativa")
    args = parser.parse_args()

    if not args.email:
        print("ERRO: email é obrigatório. Passe --email ou defina GAS_ADMIN_EMAIL no ambiente.")
        return

    password = args.password
    if not password:
        password = getpass("Senha do admin (entrada oculta): ").strip()
        if not password:
            print("Senha vazia; abortando.")
            return
        password_confirm = getpass("Confirme a senha: ").strip()
        if password != password_confirm:
            print("Senhas não conferem; abortando.")
            return

    proceed = args.yes or confirm_double(
        f"ATENÇÃO: irá criar/atualizar usuário admin com email '{args.email}'. Esta operação é sensível."
    )
    if not proceed:
        print("Operação cancelada.")
        return

    db = SessionLocal()
    try:
        ok = create_or_update_admin(db, args.name, args.email, password, force=args.force)
        if not ok:
            print("Nenhuma alteração realizada.")
        else:
            print("Pronto. Você pode fazer login com o admin criado.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
