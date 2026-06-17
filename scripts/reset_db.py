"""
Script para limpar o banco de dados completamente.
Execute com: python scripts/reset_db.py
"""

import os
from dotenv import load_dotenv
from app import app
from models import db

load_dotenv()

def reset_database():
    """Remove todas as tabelas e recria vazias."""

    with app.app_context():
        print("⚠️  Limpando banco de dados...")
        db.drop_all()
        db.create_all()
        print("✅ Banco de dados resetado com sucesso!")
        print("\n💡 Próximo passo: execute 'python seed.py' para popular com dados mockados")

if __name__ == "__main__":
    confirm = input("⚠️  Tem certeza que deseja limpar o banco de dados? (s/n): ")
    if confirm.lower() == 's':
        reset_database()
    else:
        print("❌ Operação cancelada")
