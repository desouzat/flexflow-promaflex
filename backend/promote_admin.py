"""
FlexFlow - Script para Promover Usuário Admin para Master
Atualiza o role do usuário admin@botcase.com.br para 'master'
"""

import sys
import os

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Adiciona o diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import User


def promote_user_to_master(email: str = "admin@botcase.com.br"):
    """
    Promove um usuário para o role 'master'
    
    Args:
        email: Email do usuário a ser promovido
    """
    print("\n" + "="*70)
    print("🔐 FlexFlow - Promoção de Usuário para Master")
    print("="*70)
    
    db = SessionLocal()
    try:
        # Buscar usuário
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"\n❌ Usuário com email '{email}' não encontrado!")
            print("\n💡 Verifique se o usuário existe no banco de dados.")
            return False
        
        print(f"\n📋 Usuário encontrado:")
        print(f"   • Nome: {user.name}")
        print(f"   • Email: {user.email}")
        print(f"   • Role atual: {user.role}")
        print(f"   • Tenant ID: {user.tenant_id}")
        
        # Verificar se já é master
        if user.role == "master":
            print(f"\n✅ Usuário já possui role 'master'!")
            return True
        
        # Confirmar promoção
        print(f"\n⚠️  Você está prestes a promover este usuário para 'master'.")
        print(f"   Isso dará acesso total ao módulo de Gerenciamento de Custos.")
        response = input("\nDeseja continuar? (s/N): ")
        
        if response.lower() != 's':
            print("\n❌ Operação cancelada.")
            return False
        
        # Atualizar role
        old_role = user.role
        user.role = "master"
        db.commit()
        
        print("\n" + "="*70)
        print("✅ PROMOÇÃO CONCLUÍDA COM SUCESSO!")
        print("="*70)
        print(f"\n📊 ALTERAÇÕES:")
        print(f"   • Role anterior: {old_role}")
        print(f"   • Role novo: master")
        print(f"   • Usuário: {user.email}")
        
        print(f"\n💡 PRÓXIMOS PASSOS:")
        print(f"   1. Faça logout e login novamente no sistema")
        print(f"   2. O menu 'Gerenciar Custos' agora estará visível")
        print(f"   3. Você terá acesso completo ao módulo de custos")
        print("="*70 + "\n")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Erro ao promover usuário: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
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
        print("✅ Conexão com o banco de dados estabelecida!")
        db.close()
    except Exception as e:
        print(f"\n❌ Erro ao conectar ao banco de dados:")
        print(f"   {str(e)}")
        print("\n💡 Verifique se:")
        print("   1. O Cloud SQL Proxy está rodando")
        print("   2. As credenciais estão corretas")
        print("   3. O banco de dados existe")
        sys.exit(1)
    
    # Executar promoção
    success = promote_user_to_master()
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
