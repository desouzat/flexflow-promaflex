"""
Test script to verify .env file loading
"""
from dotenv import load_dotenv
from pathlib import Path
import os

# Get the directory where this file is located (backend/)
current_dir = Path(__file__).resolve().parent
env_path = current_dir / '.env'

print("=" * 60)
print("TESTE DE CARREGAMENTO DO ARQUIVO .env")
print("=" * 60)

# Load .env file with explicit path
result = load_dotenv(dotenv_path=env_path)

print(f"\n[1] Caminho do arquivo .env: {env_path}")
print(f"[2] Arquivo .env existe: {env_path.exists()}")
print(f"[3] load_dotenv() retornou: {result}")
print(f"\n[4] DATABASE_URL carregada:")
db_url = os.getenv('DATABASE_URL', 'NAO ENCONTRADA')
print(f"    {db_url}")

# Check if it's using the correct credentials
if 'flexflow_app' in db_url and 'flexflow_prod' in db_url:
    print("\n[OK] SUCESSO: Credenciais corretas do Google Cloud detectadas!")
    print("  - Usuario: flexflow_app")
    print("  - Banco: flexflow_prod")
elif 'flexflow_user' in db_url and 'flexflow_db' in db_url:
    print("\n[ERRO] Ainda usando credenciais padrao (fallback)!")
    print("  - Usuario: flexflow_user")
    print("  - Banco: flexflow_db")
else:
    print("\n[AVISO] Credenciais nao reconhecidas")

print("\n" + "=" * 60)
