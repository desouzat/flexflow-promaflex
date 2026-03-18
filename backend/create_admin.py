"""
FlexFlow - Script de Criação de Admin
Cria um Tenant e um Usuário Admin no banco de dados com hash Argon2
"""

import sys
import os
from datetime import datetime

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Adiciona o diretório pai ao path para importar módulos do backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from passlib.context import CryptContext

from backend.database import SessionLocal, engine, Base
from backend.models import Tenant, User


# Configuração do Argon2 (mesmo usado no auth.py)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def create_tables():
    """Cria todas as tabelas no banco de dados"""
    print("🔧 Criando tabelas no banco de dados...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tabelas criadas com sucesso!")


def create_tenant_and_admin(
    tenant_name: str = "PromaFlex",
    tenant_cnpj: str = "12.345.678/0001-90",
    admin_name: str = "Administrador",
    admin_email: str = "admin@botcase.com.br",
    admin_password: str = "admin123"
):
    """
    Cria um Tenant e um Usuário Admin no banco de dados.
    
    Args:
        tenant_name: Nome do tenant (empresa)
        tenant_cnpj: CNPJ do tenant
        admin_name: Nome do usuário admin
        admin_email: Email do usuário admin
        admin_password: Senha do usuário admin (será hasheada com Argon2)
    """
    db: Session = SessionLocal()
    
    try:
        print("\n" + "="*70)
        print("🚀 FlexFlow - Criação de Tenant e Admin")
        print("="*70)
        
        # Verifica se o tenant já existe
        existing_tenant = db.query(Tenant).filter(Tenant.cnpj == tenant_cnpj).first()
        if existing_tenant:
            print(f"\n⚠️  Tenant com CNPJ {tenant_cnpj} já existe!")
            print(f"   ID: {existing_tenant.id}")
            print(f"   Nome: {existing_tenant.name}")
            tenant = existing_tenant
        else:
            # Cria o Tenant
            print(f"\n📦 Criando Tenant: {tenant_name}")
            tenant = Tenant(
                name=tenant_name,
                cnpj=tenant_cnpj,
                is_active=True
            )
            db.add(tenant)
            db.flush()  # Flush para obter o ID do tenant
            print(f"✅ Tenant criado com sucesso!")
            print(f"   ID: {tenant.id}")
            print(f"   Nome: {tenant.name}")
            print(f"   CNPJ: {tenant.cnpj}")
        
        # Verifica se o usuário admin já existe
        existing_user = db.query(User).filter(
            User.tenant_id == tenant.id,
            User.email == admin_email
        ).first()
        
        if existing_user:
            print(f"\n⚠️  Usuário com email {admin_email} já existe neste tenant!")
            print(f"   ID: {existing_user.id}")
            print(f"   Nome: {existing_user.name}")
            print(f"   Email: {existing_user.email}")
            print(f"\n💡 Dica: Use este email e senha para fazer login:")
            print(f"   Email: {admin_email}")
            print(f"   Senha: (a senha que você definiu anteriormente)")
        else:
            # Hash da senha usando Argon2
            print(f"\n👤 Criando Usuário Admin: {admin_name}")
            print(f"   🔐 Gerando hash Argon2 da senha...")
            hashed_password = pwd_context.hash(admin_password)
            print(f"   ✅ Hash gerado com sucesso!")
            
            # Cria o Usuário Admin
            admin_user = User(
                tenant_id=tenant.id,
                name=admin_name,
                email=admin_email,
                hashed_password=hashed_password,
                role="admin",
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            
            print(f"✅ Usuário Admin criado com sucesso!")
            print(f"   ID: {admin_user.id}")
            print(f"   Nome: {admin_user.name}")
            print(f"   Email: {admin_user.email}")
            print(f"   Role: {admin_user.role}")
            print(f"   Tenant ID: {admin_user.tenant_id}")
        
        # Resumo final
        print("\n" + "="*70)
        print("✅ CONFIGURAÇÃO CONCLUÍDA COM SUCESSO!")
        print("="*70)
        print("\n📋 CREDENCIAIS DE LOGIN:")
        print(f"   Email:    {admin_email}")
        print(f"   Senha:    {admin_password}")
        print("\n🌐 ACESSE O SISTEMA:")
        print(f"   Frontend: http://localhost:3000")
        print(f"   Backend:  http://localhost:8001")
        print("\n💡 PRÓXIMOS PASSOS:")
        print("   1. Acesse http://localhost:3000")
        print("   2. Faça login com as credenciais acima")
        print("   3. Comece a usar o FlexFlow!")
        print("="*70 + "\n")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Erro ao criar tenant e admin: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


def main():
    """Função principal"""
    print("\n🔍 Verificando conexão com o banco de dados...")
    
    try:
        # Testa a conexão
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        print("✅ Conexão com o banco de dados estabelecida!")
    except Exception as e:
        print(f"\n❌ Erro ao conectar ao banco de dados:")
        print(f"   {str(e)}")
        print("\n💡 Verifique se:")
        print("   1. O PostgreSQL está rodando")
        print("   2. As credenciais em DATABASE_URL estão corretas")
        print("   3. O banco de dados 'flexflow_db' existe")
        sys.exit(1)
    
    # Cria as tabelas
    create_tables()
    
    # Cria o tenant e admin com as credenciais especificadas
    create_tenant_and_admin(
        tenant_name="PromaFlex",
        tenant_cnpj="12.345.678/0001-90",
        admin_name="Administrador",
        admin_email="admin@botcase.com.br",
        admin_password="admin123"
    )


if __name__ == "__main__":
    main()
