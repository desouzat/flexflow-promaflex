# 🔄 Reset e Reseed do Banco de Dados FlexFlow

## 📋 Comandos para Limpar e Recriar os Dados

### Opção 1: Reset Completo (Recomendado)

Execute estes comandos em sequência para limpar e recriar tudo:

```bash
# 1. Conectar ao banco via Cloud SQL Proxy (se não estiver rodando)
# Abra um terminal separado e execute:
cloud_sql_proxy --port 5432 flexflow-botcase:us-central1:flexflow-db

# 2. Limpar todas as tabelas (em outro terminal)
python -c "from backend.database import engine, Base; from backend.models import *; Base.metadata.drop_all(bind=engine); print('✅ Tabelas removidas')"

# 3. Recriar as tabelas
python -c "from backend.database import engine, Base; from backend.models import *; Base.metadata.create_all(bind=engine); print('✅ Tabelas criadas')"

# 4. Criar o usuário admin
python backend/create_admin.py

# 5. Popular com dados demo
python backend/seed_showroom.py
```

### Opção 2: Apenas Limpar Pedidos (Mantém Usuários)

Se você quer manter os usuários e apenas recriar os pedidos:

```bash
# 1. Limpar apenas pedidos
python -c "from backend.database import SessionLocal; from backend.models import PurchaseOrder, OrderItem, AuditLog; db = SessionLocal(); db.query(AuditLog).delete(); db.query(OrderItem).delete(); db.query(PurchaseOrder).delete(); db.commit(); print('✅ Pedidos removidos'); db.close()"

# 2. Popular com dados demo
python backend/seed_showroom.py
```

### Opção 3: Script Python Completo

Crie um arquivo `reset_db.py` na raiz do projeto:

```python
"""
Script para resetar o banco de dados FlexFlow
"""
import sys
from backend.database import engine, Base, SessionLocal
from backend.models import Tenant, User, PurchaseOrder, OrderItem, AuditLog

def reset_database():
    print("\n🔄 Iniciando reset do banco de dados...")
    
    # Opção 1: Drop e Create All
    print("\n1️⃣  Removendo todas as tabelas...")
    Base.metadata.drop_all(bind=engine)
    print("✅ Tabelas removidas")
    
    print("\n2️⃣  Criando tabelas...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tabelas criadas")
    
    print("\n✅ Reset concluído!")
    print("\n📝 Próximos passos:")
    print("   1. Execute: python backend/create_admin.py")
    print("   2. Execute: python backend/seed_showroom.py")

def clear_orders_only():
    print("\n🔄 Limpando apenas pedidos...")
    db = SessionLocal()
    try:
        # Deletar em ordem (por causa das foreign keys)
        db.query(AuditLog).delete()
        db.query(OrderItem).delete()
        db.query(PurchaseOrder).delete()
        db.commit()
        print("✅ Pedidos removidos")
        print("\n📝 Próximo passo:")
        print("   Execute: python backend/seed_showroom.py")
    except Exception as e:
        db.rollback()
        print(f"❌ Erro: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--orders-only":
        clear_orders_only()
    else:
        reset_database()
```

Depois execute:

```bash
# Reset completo
python reset_db.py

# Ou apenas limpar pedidos
python reset_db.py --orders-only
```

## 🎯 Comando Rápido (Tudo em Um)

Para Windows (cmd.exe):

```cmd
python -c "from backend.database import engine, Base; from backend.models import *; Base.metadata.drop_all(bind=engine); Base.metadata.create_all(bind=engine); print('✅ DB Reset')" && python backend/create_admin.py && python backend/seed_showroom.py
```

Para PowerShell:

```powershell
python -c "from backend.database import engine, Base; from backend.models import *; Base.metadata.drop_all(bind=engine); Base.metadata.create_all(bind=engine); print('✅ DB Reset')"; python backend/create_admin.py; python backend/seed_showroom.py
```

## 📊 Verificar Dados Após Reset

```bash
# Verificar quantos pedidos foram criados
python -c "from backend.database import SessionLocal; from backend.models import PurchaseOrder; db = SessionLocal(); count = db.query(PurchaseOrder).count(); print(f'📦 Total de pedidos: {count}'); db.close()"

# Verificar status dos pedidos
python -c "from backend.database import SessionLocal; from backend.models import PurchaseOrder; db = SessionLocal(); pos = db.query(PurchaseOrder).all(); [print(f'{po.po_number}: {po.status_macro}') for po in pos]; db.close()"
```

## ⚠️ Notas Importantes

1. **Cloud SQL Proxy**: Certifique-se de que o Cloud SQL Proxy está rodando antes de executar qualquer comando
2. **Backup**: Estes comandos são DESTRUTIVOS. Use apenas em ambiente de desenvolvimento
3. **Status Inicial**: Os pedidos são criados com status `DRAFT` (que aparece como "Pendente" no Kanban)
4. **Uploads**: A pasta `backend/uploads` foi criada para anexos de arquivos

## 🚀 Após o Reset

1. Acesse: http://localhost:3000
2. Login: admin@botcase.com.br / admin123
3. Navegue para o Kanban - você verá os cards na coluna "Pendente"
4. Navegue para o Dashboard - você verá as métricas dos pedidos

## 🔍 Troubleshooting

### Erro: "relation does not exist"
```bash
# Recrie as tabelas
python -c "from backend.database import engine, Base; from backend.models import *; Base.metadata.create_all(bind=engine)"
```

### Erro: "Tenant PromaFlex não encontrado"
```bash
# Recrie o admin
python backend/create_admin.py
```

### Kanban vazio após seed
```bash
# Verifique se os pedidos foram criados
python -c "from backend.database import SessionLocal; from backend.models import PurchaseOrder; db = SessionLocal(); print(f'Pedidos: {db.query(PurchaseOrder).count()}'); db.close()"
```
