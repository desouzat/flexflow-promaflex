# FlexFlow - Implementação dos Modelos SQLAlchemy

## Arquivo: backend/requirements.txt

```txt
# FastAPI e servidor ASGI
fastapi==0.109.0
uvicorn==0.27.0

# Banco de dados
sqlalchemy==2.0.25
psycopg2-binary==2.9.9

# Autenticação e segurança
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4

# Validação e utilitários
pydantic[email]==2.5.3
python-multipart==0.0.6

# Migrações de banco de dados
alembic==1.13.1

# Variáveis de ambiente
python-dotenv==1.0.0
```

---

## Arquivo: backend/models.py

```python
"""
FlexFlow - Modelos de Banco de Dados
Sistema de gerenciamento de pedidos de compra com Multi-tenancy
"""

from datetime import datetime
from typing import Optional, List
import uuid
import hashlib

from sqlalchemy import (
    Column, String, Boolean, Integer, Numeric, DateTime, 
    ForeignKey, CheckConstraint, Index, Text, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, declarative_base, Mapped, mapped_column
from sqlalchemy.sql import func

# Base para todos os modelos
Base = declarative_base()


# ============================================================================
# MODELO: Tenant (Multi-tenancy)
# ============================================================================

class Tenant(Base):
    """
    Modelo de Tenant para Multi-tenancy.
    Representa uma empresa/organização no sistema.
    """
    __tablename__ = "tenants"
    
    # Colunas
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cnpj: Mapped[str] = mapped_column(String(18), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )
    
    # Relacionamentos
    users: Mapped[List["User"]] = relationship(
        "User", 
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    purchase_orders: Mapped[List["PurchaseOrder"]] = relationship(
        "PurchaseOrder",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    
    # Índices
    __table_args__ = (
        Index('idx_tenant_cnpj', 'cnpj'),
        Index('idx_tenant_is_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<Tenant(id={self.id}, name={self.name}, cnpj={self.cnpj})>"


# ============================================================================
# MODELO: User
# ============================================================================

class User(Base):
    """
    Modelo de Usuário com isolamento por tenant.
    """
    __tablename__ = "users"
    
    # Colunas
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    area_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), 
        nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )
    
    # Relacionamentos
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    created_purchase_orders: Mapped[List["PurchaseOrder"]] = relationship(
        "PurchaseOrder",
        back_populates="creator",
        foreign_keys="PurchaseOrder.created_by"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="changed_by_user",
        foreign_keys="AuditLog.changed_by"
    )
    
    # Índices e Constraints
    __table_args__ = (
        Index('idx_user_tenant_id', 'tenant_id'),
        Index('idx_user_email', 'email'),
        Index('idx_user_tenant_email', 'tenant_id', 'email', unique=True),
        Index('idx_user_role', 'role'),
        Index('idx_user_is_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, tenant_id={self.tenant_id})>"


# ============================================================================
# MODELO: PurchaseOrder (Pai)
# ============================================================================

class PurchaseOrder(Base):
    """
    Modelo de Pedido de Compra (Pai).
    Relacionamento 1:N com OrderItem.
    """
    __tablename__ = "purchase_orders"
    
    # Status macro permitidos
    STATUS_DRAFT = "DRAFT"
    STATUS_SUBMITTED = "SUBMITTED"
    STATUS_APPROVED = "APPROVED"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_CANCELLED = "CANCELLED"
    
    VALID_STATUSES = [
        STATUS_DRAFT, STATUS_SUBMITTED, STATUS_APPROVED,
        STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_CANCELLED
    ]
    
    # Colunas
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )
    po_number: Mapped[str] = mapped_column(String(100), nullable=False)
    status_macro: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Relacionamentos
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="purchase_orders")
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="created_purchase_orders",
        foreign_keys=[created_by]
    )
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="purchase_order",
        cascade="all, delete-orphan"
    )
    
    # Índices e Constraints
    __table_args__ = (
        Index('idx_po_tenant_id', 'tenant_id'),
        Index('idx_po_tenant_po_number', 'tenant_id', 'po_number', unique=True),
        Index('idx_po_status_macro', 'status_macro'),
        Index('idx_po_created_by', 'created_by'),
        CheckConstraint(
            f"status_macro IN {tuple(VALID_STATUSES)}",
            name='check_po_status_macro'
        ),
    )
    
    def __repr__(self):
        return f"<PurchaseOrder(id={self.id}, po_number={self.po_number}, status={self.status_macro})>"


# ============================================================================
# MODELO: OrderItem (Filho)
# ============================================================================

class OrderItem(Base):
    """
    Modelo de Item de Pedido (Filho).
    Relacionamento N:1 com PurchaseOrder.
    """
    __tablename__ = "order_items"
    
    # Status de item permitidos
    STATUS_PENDING = "PENDING"
    STATUS_ORDERED = "ORDERED"
    STATUS_RECEIVED = "RECEIVED"
    STATUS_QUALITY_CHECK = "QUALITY_CHECK"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CANCELLED = "CANCELLED"
    
    VALID_STATUSES = [
        STATUS_PENDING, STATUS_ORDERED, STATUS_RECEIVED,
        STATUS_QUALITY_CHECK, STATUS_APPROVED, STATUS_REJECTED, STATUS_CANCELLED
    ]
    
    # Colunas
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    po_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status_item: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )
    
    # Relacionamentos
    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder",
        back_populates="items"
    )
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="order_items")
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="order_item",
        cascade="all, delete-orphan"
    )
    
    # Índices e Constraints
    __table_args__ = (
        Index('idx_item_po_id', 'po_id'),
        Index('idx_item_tenant_id', 'tenant_id'),
        Index('idx_item_sku', 'sku'),
        Index('idx_item_status', 'status_item'),
        CheckConstraint('quantity > 0', name='check_item_quantity_positive'),
        CheckConstraint('price >= 0', name='check_item_price_non_negative'),
        CheckConstraint(
            f"status_item IN {tuple(VALID_STATUSES)}",
            name='check_item_status'
        ),
    )
    
    def __repr__(self):
        return f"<OrderItem(id={self.id}, sku={self.sku}, quantity={self.quantity}, status={self.status_item})>"


# ============================================================================
# MODELO: AuditLog
# ============================================================================

class AuditLog(Base):
    """
    Modelo de Log de Auditoria com blockchain simplificado.
    Rastreia todas as mudanças de status em OrderItem.
    """
    __tablename__ = "audit_logs"
    
    # Colunas
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False
    )
    from_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Relacionamentos
    order_item: Mapped["OrderItem"] = relationship(
        "OrderItem",
        back_populates="audit_logs"
    )
    changed_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs",
        foreign_keys=[changed_by]
    )
    
    # Índices
    __table_args__ = (
        Index('idx_audit_item_id', 'item_id'),
        Index('idx_audit_created_at', 'created_at'),
        Index('idx_audit_hash', 'hash'),
        Index('idx_audit_changed_by', 'changed_by'),
    )
    
    @staticmethod
    def calculate_hash(
        item_id: uuid.UUID,
        from_status: Optional[str],
        to_status: str,
        timestamp: datetime,
        previous_hash: Optional[str],
        changed_by: Optional[uuid.UUID]
    ) -> str:
        """
        Calcula o hash SHA-256 para o registro de auditoria.
        
        Args:
            item_id: ID do item
            from_status: Status anterior
            to_status: Novo status
            timestamp: Timestamp da mudança
            previous_hash: Hash do registro anterior
            changed_by: ID do usuário que fez a mudança
            
        Returns:
            Hash SHA-256 em formato hexadecimal
        """
        data = (
            str(item_id) +
            (from_status or "") +
            to_status +
            timestamp.isoformat() +
            (previous_hash or "") +
            (str(changed_by) if changed_by else "")
        )
        return hashlib.sha256(data.encode()).hexdigest()
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, item_id={self.item_id}, {self.from_status}->{self.to_status})>"


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def get_last_audit_hash(session, item_id: uuid.UUID) -> Optional[str]:
    """
    Obtém o hash do último registro de auditoria para um item.
    
    Args:
        session: Sessão do SQLAlchemy
        item_id: ID do item
        
    Returns:
        Hash do último registro ou None se não houver registros
    """
    last_log = (
        session.query(AuditLog)
        .filter(AuditLog.item_id == item_id)
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    return last_log.hash if last_log else None


def create_audit_log(
    session,
    item_id: uuid.UUID,
    from_status: Optional[str],
    to_status: str,
    changed_by: Optional[uuid.UUID] = None,
    metadata: Optional[dict] = None
) -> AuditLog:
    """
    Cria um novo registro de auditoria com hash calculado.
    
    Args:
        session: Sessão do SQLAlchemy
        item_id: ID do item
        from_status: Status anterior
        to_status: Novo status
        changed_by: ID do usuário que fez a mudança
        metadata: Dados adicionais
        
    Returns:
        Objeto AuditLog criado
    """
    timestamp = datetime.utcnow()
    previous_hash = get_last_audit_hash(session, item_id)
    
    hash_value = AuditLog.calculate_hash(
        item_id=item_id,
        from_status=from_status,
        to_status=to_status,
        timestamp=timestamp,
        previous_hash=previous_hash,
        changed_by=changed_by
    )
    
    audit_log = AuditLog(
        item_id=item_id,
        from_status=from_status,
        to_status=to_status,
        hash=hash_value,
        previous_hash=previous_hash,
        changed_by=changed_by,
        metadata=metadata,
        created_at=timestamp
    )
    
    session.add(audit_log)
    return audit_log


def verify_audit_chain(session, item_id: uuid.UUID) -> bool:
    """
    Verifica a integridade da cadeia de auditoria para um item.
    
    Args:
        session: Sessão do SQLAlchemy
        item_id: ID do item
        
    Returns:
        True se a cadeia está íntegra, False caso contrário
    """
    logs = (
        session.query(AuditLog)
        .filter(AuditLog.item_id == item_id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    
    if not logs:
        return True
    
    previous_hash = None
    for log in logs:
        # Verifica se o previous_hash está correto
        if log.previous_hash != previous_hash:
            return False
        
        # Recalcula o hash e verifica
        calculated_hash = AuditLog.calculate_hash(
            item_id=log.item_id,
            from_status=log.from_status,
            to_status=log.to_status,
            timestamp=log.created_at,
            previous_hash=log.previous_hash,
            changed_by=log.changed_by
        )
        
        if calculated_hash != log.hash:
            return False
        
        previous_hash = log.hash
    
    return True
```

---

## Características Implementadas

### ✅ Multi-tenancy
- Todas as tabelas principais incluem `tenant_id`
- Relacionamentos CASCADE para manter integridade
- Índices compostos para garantir unicidade por tenant

### ✅ Relacionamento 1:N
- `PurchaseOrder` (Pai) → `OrderItem` (Filho)
- Cascade delete configurado
- Back-references bidirecionais

### ✅ UUID como Chave Primária
- Todas as tabelas usam UUID v4
- Geração automática via `uuid.uuid4()`

### ✅ Sistema de Auditoria
- Hash SHA-256 encadeado
- Função auxiliar para calcular hash
- Função para verificar integridade da cadeia
- Metadata JSONB para dados adicionais

### ✅ Validações e Constraints
- Check constraints para valores positivos
- Enums para status válidos
- Índices únicos compostos
- Foreign keys com ON DELETE apropriados

### ✅ Timestamps Automáticos
- `created_at` com server_default
- `updated_at` com onupdate automático

---

## Próximos Arquivos a Criar

1. **backend/database.py** - Configuração da conexão com PostgreSQL
2. **backend/config.py** - Configurações e variáveis de ambiente
3. **backend/schemas.py** - Schemas Pydantic para validação
4. **backend/crud.py** - Operações CRUD com isolamento de tenant
5. **backend/main.py** - Aplicação FastAPI principal
6. **alembic.ini** - Configuração de migrations
7. **alembic/env.py** - Ambiente de migrations
