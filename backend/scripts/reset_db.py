############################################
### SCRIPT PARA RESETAR O BANCO DE DADOS ###
############################################

#!/usr/bin/env python3 
import shutil
import os
import sys
from pathlib import Path

# garantir que backend/ esteja no path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app import models  # importa os modelos para popular Base
from app.database import engine, Base, DATABASE_URL  # ajuste se o nome for diferente

# SQL helper (import local)
from sqlalchemy import text

# Ajuste: se estiver usando sqlite, cria um backup do arquivo
def backup_sqlite(db_url: str):
    if db_url.startswith("sqlite:///"):
        # sqlite:///./dev.db  -> pega o caminho relativo após sqlite:///
        path = db_url.replace("sqlite:///", "")
        p = Path(path)
        if p.exists():
            backup_path = p.with_suffix(p.suffix + ".bak")
            shutil.copy(p, backup_path)
            print(f"Backup criado: {backup_path}")
        else:
            print("Arquivo sqlite não encontrado; nada a fazer no backup.")

def confirm():
    ans = input("ATENÇÃO: isso DROPARÁ e recriará todas as tabelas (dados serão perdidos). Digite 'yes' para confirmar: ")
    if ans.lower() == "yes":
        second_ans = input("Digite 'secondyes' para confirmar definitivamente: ")
        if second_ans.lower() != "secondyes":
            return False
    return ans.lower() == "yes"

def main():
    # backup (apenas sqlite)
    backup_sqlite(os.getenv("DATABASE_URL", "sqlite:///./dev.db"))
    if not confirm():
        print("Operação cancelada.")
        return

    # Dropar / recriar dependendo do tipo de DB
    db_url = os.getenv("DATABASE_URL", DATABASE_URL or "")

    if db_url.startswith("sqlite:///"):
        # SQLite: comportamento antigo
        print("Dropando tabelas (SQLite) via Base.metadata.drop_all)...")
        Base.metadata.drop_all(bind=engine)
    else:
        # Presumivelmente Postgres (ou outro RDBMS). Para Postgres usamos DROP SCHEMA ... CASCADE
        # Isso remove todas as tabelas/constraints no schema public; em seguida recriamos com create_all.
        # ATENÇÃO: isso remove TUDO no schema (comportamento equivalente ao reset desejado).
        print("Detectado DB não-SQLite. Executando DROP SCHEMA public CASCADE ... (Postgres).")
        try:
            # usar isolamento/autocommit para as operações DDL em alguns drivers
            with engine.connect() as conn:
                conn = conn.execution_options(isolation_level="AUTOCOMMIT")
                conn.execute(text("DROP SCHEMA public CASCADE"))
                conn.execute(text("CREATE SCHEMA public"))
                print("DROP SCHEMA public CASCADE e CREATE SCHEMA public executados com sucesso.")
        except Exception as e:
            print("Falha ao executar DROP SCHEMA CASCADE no banco. Erro:", repr(e))
            print("Como fallback, tentando Base.metadata.drop_all (pode falhar por dependências).")
            Base.metadata.drop_all(bind=engine)

    # criar as tabelas a partir dos modelos
    print("Criando tabelas...")
    Base.metadata.create_all(bind=engine)
    print("Feito. Tabelas recriadas.")

if __name__ == "__main__":
    main()
