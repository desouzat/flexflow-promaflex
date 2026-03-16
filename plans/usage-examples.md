# FlexFlow - Exemplos de Uso dos Modelos

## 📚 Guia de Uso Prático

Este documento fornece exemplos práticos de como usar os modelos SQLAlchemy do FlexFlow.

---

## 🔧 Configuração Inicial

### 1. Arquivo: backend/database.py

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
import os

# URL de conexão do PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/flexflow"
)

# Criar engine
engine = create_engine(
    DATABASE_URL,
    echo=True,  # Log SQL queries (desabilitar em produção)
    pool_pre_ping=True,  # Verificar conexões antes de usar
    pool_size=10,
    max_overflow=20
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Criar todas as tabelas
def init_db():
    Base.metadata.create_all(bind=engine)

# Dependency para FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 2. Arquivo: backend/config.py

```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/flexflow"
    
    # Security
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Application
    APP_NAME: str = "FlexFlow"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 3. Arquivo: .env.example

```env
# Database Configuration
DATABASE_URL=postgresql://flexflow_user:secure_password@localhost:5432/flexflow_db

# Security
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application
APP_NAME=FlexFlow
DEBUG=True
```

---

## 📝 Exemplos de Uso

### Exemplo 1: Criar um Tenant

```python
from sqlalchemy.orm import Session
from models import Tenant
import uuid

def create_tenant(db: Session, name: str, cnpj: str) -> Tenant:
    """Cria um novo tenant."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name=name,
        cnpj=cnpj,
        is_active=True
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant

# Uso
with SessionLocal() as db:
    tenant = create_tenant(
        db=db,
        name="Empresa ABC Ltda",
        cnpj="12.345.678/0001-90"
    )
    print(f"Tenant criado: {tenant.id}")
```

### Exemplo 2: Criar um Usuário

```python
from models import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_user(
    db: Session,
    tenant_id: uuid.UUID,
    name: str,
    email: str,
    password: str,
    role: str,
    area_id: Optional[uuid.UUID] = None
) -> User:
    """Cria um novo usuário."""
    hashed_password = pwd_context.hash(password)
    
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        email=email,
        hashed_password=hashed_password,
        role=role,
        area_id=area_id,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

# Uso
with SessionLocal() as db:
    user = create_user(
        db=db,
        tenant_id=tenant.id,
        name="João Silva",
        email="joao@empresaabc.com",
        password="senha123",
        role="ADMIN"
    )
    print(f"Usuário criado: {user.id}")
```

### Exemplo 3: Criar Purchase Order com Itens

```python
from models import PurchaseOrder, OrderItem

def create_purchase_order_with_items(
    db: Session,
    tenant_id: uuid.UUID,
    po_number: str,
    created_by: uuid.UUID,
    items: list[dict]
) -> PurchaseOrder:
    """Cria uma PO com seus itens."""
    
    # Criar PO
    po = PurchaseOrder(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        po_number=po_number,
        status_macro=PurchaseOrder.STATUS_DRAFT,
        created_by=created_by
    )
    db.add(po)
    db.flush()  # Obter o ID da PO antes de criar itens
    
    # Criar itens
    for item_data in items:
        item = OrderItem(
            id=uuid.uuid4(),
            po_id=po.id,
            tenant_id=tenant_id,
            sku=item_data["sku"],
            quantity=item_data["quantity"],
            price=item_data["price"],
            status_item=OrderItem.STATUS_PENDING
        )
        db.add(item)
    
    db.commit()
    db.refresh(po)
    return po

# Uso
with SessionLocal() as db:
    items = [
        {"sku": "PROD-001", "quantity": 10, "price": 99.90},
        {"sku": "PROD-002", "quantity": 5, "price": 149.90},
        {"sku": "PROD-003", "quantity": 20, "price": 29.90}
    ]
    
    po = create_purchase_order_with_items(
        db=db,
        tenant_id=tenant.id,
        po_number="PO-2026-001",
        created_by=user.id,
        items=items
    )
    print(f"PO criada: {po.po_number} com {len(po.items)} itens")
```

### Exemplo 4: Atualizar Status de Item com Auditoria

```python
from models import OrderItem, create_audit_log

def update_item_status(
    db: Session,
    item_id: uuid.UUID,
    new_status: str,
    changed_by: uuid.UUID,
    metadata: Optional[dict] = None
) -> OrderItem:
    """Atualiza status de um item e cria log de auditoria."""
    
    # Buscar item
    item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not item:
        raise ValueError("Item não encontrado")
    
    # Guardar status anterior
    old_status = item.status_item
    
    # Atualizar status
    item.status_item = new_status
    
    # Criar log de auditoria
    audit_log = create_audit_log(
        session=db,
        item_id=item.id,
        from_status=old_status,
        to_status=new_status,
        changed_by=changed_by,
        metadata=metadata
    )
    
    db.commit()
    db.refresh(item)
    
    print(f"Status atualizado: {old_status} → {new_status}")
    print(f"Hash do log: {audit_log.hash}")
    
    return item

# Uso
with SessionLocal() as db:
    item = po.items[0]
    
    # Mudança 1: PENDING → ORDERED
    update_item_status(
        db=db,
        item_id=item.id,
        new_status=OrderItem.STATUS_ORDERED,
        changed_by=user.id,
        metadata={"note": "Pedido enviado ao fornecedor"}
    )
    
    # Mudança 2: ORDERED → RECEIVED
    update_item_status(
        db=db,
        item_id=item.id,
        new_status=OrderItem.STATUS_RECEIVED,
        changed_by=user.id,
        metadata={"note": "Recebido em 16/03/2026"}
    )
```

### Exemplo 5: Verificar Integridade da Auditoria

```python
from models import verify_audit_chain

def check_item_audit_integrity(db: Session, item_id: uuid.UUID) -> bool:
    """Verifica se a cadeia de auditoria está íntegra."""
    is_valid = verify_audit_chain(db, item_id)
    
    if is_valid:
        print(f"✅ Cadeia de auditoria do item {item_id} está íntegra")
    else:
        print(f"❌ ALERTA: Cadeia de auditoria do item {item_id} foi adulterada!")
    
    return is_valid

# Uso
with SessionLocal() as db:
    check_item_audit_integrity(db, item.id)
```

### Exemplo 6: Consultar Histórico de Auditoria

```python
from models import AuditLog

def get_item_audit_history(db: Session, item_id: uuid.UUID) -> list[AuditLog]:
    """Obtém histórico completo de auditoria de um item."""
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.item_id == item_id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    
    print(f"\n📋 Histórico de Auditoria - Item {item_id}")
    print("=" * 80)
    
    for i, log in enumerate(logs, 1):
        print(f"\n{i}. {log.from_status or 'INÍCIO'} → {log.to_status}")
        print(f"   Data: {log.created_at}")
        print(f"   Hash: {log.hash[:16]}...")
        print(f"   Hash Anterior: {log.previous_hash[:16] if log.previous_hash else 'N/A'}...")
        if log.metadata:
            print(f"   Metadata: {log.metadata}")
    
    return logs

# Uso
with SessionLocal() as db:
    history = get_item_audit_history(db, item.id)
```

### Exemplo 7: Consultas com Isolamento de Tenant

```python
def get_tenant_purchase_orders(
    db: Session,
    tenant_id: uuid.UUID,
    status: Optional[str] = None
) -> list[PurchaseOrder]:
    """Busca POs de um tenant específico."""
    query = db.query(PurchaseOrder).filter(
        PurchaseOrder.tenant_id == tenant_id
    )
    
    if status:
        query = query.filter(PurchaseOrder.status_macro == status)
    
    return query.all()

def get_tenant_items_by_status(
    db: Session,
    tenant_id: uuid.UUID,
    status: str
) -> list[OrderItem]:
    """Busca itens de um tenant por status."""
    return (
        db.query(OrderItem)
        .filter(
            OrderItem.tenant_id == tenant_id,
            OrderItem.status_item == status
        )
        .all()
    )

# Uso
with SessionLocal() as db:
    # Todas as POs em rascunho
    draft_pos = get_tenant_purchase_orders(
        db=db,
        tenant_id=tenant.id,
        status=PurchaseOrder.STATUS_DRAFT
    )
    
    # Todos os itens pendentes
    pending_items = get_tenant_items_by_status(
        db=db,
        tenant_id=tenant.id,
        status=OrderItem.STATUS_PENDING
    )
```

### Exemplo 8: Relacionamentos e Joins

```python
def get_po_with_items_and_creator(
    db: Session,
    po_id: uuid.UUID,
    tenant_id: uuid.UUID
) -> Optional[PurchaseOrder]:
    """Busca PO com itens e informações do criador."""
    po = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.id == po_id,
            PurchaseOrder.tenant_id == tenant_id
        )
        .first()
    )
    
    if not po:
        return None
    
    print(f"\n📦 Purchase Order: {po.po_number}")
    print(f"Status: {po.status_macro}")
    print(f"Criado por: {po.creator.name if po.creator else 'N/A'}")
    print(f"Data: {po.created_at}")
    print(f"\nItens ({len(po.items)}):")
    
    for item in po.items:
        print(f"  - {item.sku}: {item.quantity}x R$ {item.price} = R$ {item.quantity * item.price}")
        print(f"    Status: {item.status_item}")
    
    total = sum(item.quantity * item.price for item in po.items)
    print(f"\nTotal: R$ {total:.2f}")
    
    return po

# Uso
with SessionLocal() as db:
    po_details = get_po_with_items_and_creator(
        db=db,
        po_id=po.id,
        tenant_id=tenant.id
    )
```

### Exemplo 9: Estatísticas por Tenant

```python
from sqlalchemy import func

def get_tenant_statistics(db: Session, tenant_id: uuid.UUID) -> dict:
    """Obtém estatísticas de um tenant."""
    
    # Total de POs
    total_pos = (
        db.query(func.count(PurchaseOrder.id))
        .filter(PurchaseOrder.tenant_id == tenant_id)
        .scalar()
    )
    
    # Total de itens
    total_items = (
        db.query(func.count(OrderItem.id))
        .filter(OrderItem.tenant_id == tenant_id)
        .scalar()
    )
    
    # Valor total
    total_value = (
        db.query(func.sum(OrderItem.quantity * OrderItem.price))
        .filter(OrderItem.tenant_id == tenant_id)
        .scalar() or 0
    )
    
    # Itens por status
    items_by_status = (
        db.query(OrderItem.status_item, func.count(OrderItem.id))
        .filter(OrderItem.tenant_id == tenant_id)
        .group_by(OrderItem.status_item)
        .all()
    )
    
    stats = {
        "total_pos": total_pos,
        "total_items": total_items,
        "total_value": float(total_value),
        "items_by_status": {status: count for status, count in items_by_status}
    }
    
    print(f"\n📊 Estatísticas do Tenant")
    print(f"Total de POs: {stats['total_pos']}")
    print(f"Total de Itens: {stats['total_items']}")
    print(f"Valor Total: R$ {stats['total_value']:.2f}")
    print(f"\nItens por Status:")
    for status, count in stats['items_by_status'].items():
        print(f"  {status}: {count}")
    
    return stats

# Uso
with SessionLocal() as db:
    stats = get_tenant_statistics(db, tenant.id)
```

### Exemplo 10: Deletar PO com Cascade

```python
def delete_purchase_order(
    db: Session,
    po_id: uuid.UUID,
    tenant_id: uuid.UUID
) -> bool:
    """Deleta uma PO e todos os seus itens (cascade)."""
    
    po = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.id == po_id,
            PurchaseOrder.tenant_id == tenant_id
        )
        .first()
    )
    
    if not po:
        return False
    
    items_count = len(po.items)
    po_number = po.po_number
    
    db.delete(po)
    db.commit()
    
    print(f"✅ PO {po_number} deletada com {items_count} itens")
    
    return True

# Uso
with SessionLocal() as db:
    delete_purchase_order(db, po.id, tenant.id)
```

---

## 🔒 Middleware de Tenant Isolation

```python
from fastapi import Request, HTTPException, Depends
from jose import jwt, JWTError

async def get_current_tenant(request: Request) -> uuid.UUID:
    """Extrai tenant_id do token JWT."""
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(status_code=401, detail="Token não fornecido")
    
    try:
        token = token.replace("Bearer ", "")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        tenant_id = payload.get("tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=401, detail="Tenant não identificado")
        
        return uuid.UUID(tenant_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

# Uso em endpoints FastAPI
from fastapi import APIRouter, Depends

router = APIRouter()

@router.get("/purchase-orders")
async def list_purchase_orders(
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant)
):
    """Lista POs do tenant autenticado."""
    pos = get_tenant_purchase_orders(db, tenant_id)
    return pos
```

---

## 🧪 Testes Unitários

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Tenant, User, PurchaseOrder, OrderItem

# Configurar banco de teste
TEST_DATABASE_URL = "postgresql://test:test@localhost:5432/flexflow_test"
engine = create_engine(TEST_DATABASE_URL)
TestSessionLocal = sessionmaker(bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_create_tenant(db):
    tenant = Tenant(name="Test Corp", cnpj="12.345.678/0001-90")
    db.add(tenant)
    db.commit()
    
    assert tenant.id is not None
    assert tenant.is_active is True

def test_tenant_isolation(db):
    # Criar dois tenants
    tenant1 = Tenant(name="Tenant 1", cnpj="11.111.111/0001-11")
    tenant2 = Tenant(name="Tenant 2", cnpj="22.222.222/0001-22")
    db.add_all([tenant1, tenant2])
    db.commit()
    
    # Criar POs para cada tenant
    po1 = PurchaseOrder(tenant_id=tenant1.id, po_number="PO-001", status_macro="DRAFT")
    po2 = PurchaseOrder(tenant_id=tenant2.id, po_number="PO-001", status_macro="DRAFT")
    db.add_all([po1, po2])
    db.commit()
    
    # Verificar isolamento
    tenant1_pos = db.query(PurchaseOrder).filter(PurchaseOrder.tenant_id == tenant1.id).all()
    assert len(tenant1_pos) == 1
    assert tenant1_pos[0].po_number == "PO-001"

def test_cascade_delete(db):
    tenant = Tenant(name="Test", cnpj="12.345.678/0001-90")
    db.add(tenant)
    db.commit()
    
    po = PurchaseOrder(tenant_id=tenant.id, po_number="PO-001", status_macro="DRAFT")
    db.add(po)
    db.commit()
    
    item = OrderItem(
        po_id=po.id,
        tenant_id=tenant.id,
        sku="TEST-001",
        quantity=10,
        price=99.90,
        status_item="PENDING"
    )
    db.add(item)
    db.commit()
    
    # Deletar PO
    db.delete(po)
    db.commit()
    
    # Verificar que item foi deletado
    items = db.query(OrderItem).filter(OrderItem.po_id == po.id).all()
    assert len(items) == 0
```

---

## 📚 Recursos Adicionais

- [Documentação SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Alembic Migrations](https://alembic.sqlalchemy.org/)

---

**Próximo Passo**: Mudar para o modo **Code** para implementar os arquivos!
