"""
FlexFlow - Modelos de Banco de Dados
Sistema de gerenciamento de pedidos de compra com Multi-tenancy
"""

from datetime import datetime
from typing import Optional, List
import uuid
import hashlib
import enum

from sqlalchemy import (
    Column, String, Boolean, Integer, Numeric, DateTime,
    ForeignKey, CheckConstraint, Index, Text, JSON, Enum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


# ============================================================================
# ENUMS
# ============================================================================

class PackagingType(str, enum.Enum):
    """Tipos de embalagem para produtos"""
    CAIXA = "CAIXA"
    SACO = "SACO"
    PALLET = "PALLET"
    GRANEL = "GRANEL"
    OUTRO = "OUTRO"


class ProductionImpediment(str, enum.Enum):
    """Impedimentos de produção estruturados"""
    FALTA_MATERIA_PRIMA = "FALTA_MATERIA_PRIMA"
    FALTA_INSUMO = "FALTA_INSUMO"
    EQUIPAMENTO_QUEBRADO = "EQUIPAMENTO_QUEBRADO"
    FALTA_MO = "FALTA_MO"  # Mão de obra
    PROBLEMA_QUALIDADE = "PROBLEMA_QUALIDADE"
    AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO"
    OUTRO = "OUTRO"


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
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
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
    is_exception: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
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
        Index('idx_audit_is_exception', 'is_exception'),
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
    last_log = session.query(AuditLog).filter(
        AuditLog.item_id == item_id
    ).order_by(AuditLog.created_at.desc()).first()
    
    return last_log.hash if last_log else None


# ============================================================================
# MODELO: MaterialCost
# ============================================================================

class MaterialCost(Base):
    """
    Modelo de Custos de Material.
    Gerencia custos de matéria-prima e rendimento por SKU.
    Acesso exclusivo para role MASTER.
    """
    __tablename__ = "material_costs"
    
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
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    custo_mp_kg: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Custo de matéria-prima por kg"
    )
    rendimento: Mapped[float] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        comment="Rendimento em kg por unidade"
    )
    indice_impostos: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=22.25,
        comment="Índice de impostos em percentual (padrão 22.25%)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Relacionamentos
    tenant: Mapped["Tenant"] = relationship("Tenant")
    updated_by_user: Mapped[Optional["User"]] = relationship("User")
    
    # Índices e Constraints
    __table_args__ = (
        Index('idx_material_cost_tenant_id', 'tenant_id'),
        Index('idx_material_cost_sku', 'sku'),
        Index('idx_material_cost_tenant_sku', 'tenant_id', 'sku', unique=True),
        CheckConstraint('custo_mp_kg >= 0', name='check_custo_mp_kg_non_negative'),
        CheckConstraint('rendimento > 0', name='check_rendimento_positive'),
        CheckConstraint('indice_impostos >= 0 AND indice_impostos <= 100', name='check_indice_impostos_range'),
    )
    
    def __repr__(self):
        return f"<MaterialCost(id={self.id}, sku={self.sku}, nome={self.nome})>"


# ============================================================================
# MODELO: GlobalConfig
# ============================================================================

class GlobalConfig(Base):
    """
    Modelo de Configuração Global do Sistema.
    Armazena parâmetros configuráveis como multiplicadores de SLA.
    Acesso exclusivo para role MASTER.
    """
    __tablename__ = "global_config"
    
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
    config_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Chave de configuração (ex: replacement_sla_multiplier)"
    )
    config_value: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Valor da configuração (armazenado como string)"
    )
    config_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="string",
        comment="Tipo do valor: string, float, int, bool, json"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Descrição da configuração"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Relacionamentos
    tenant: Mapped["Tenant"] = relationship("Tenant")
    updated_by_user: Mapped[Optional["User"]] = relationship("User")
    
    # Índices e Constraints
    __table_args__ = (
        Index('idx_global_config_tenant_id', 'tenant_id'),
        Index('idx_global_config_key', 'config_key'),
        Index('idx_global_config_tenant_key', 'tenant_id', 'config_key', unique=True),
    )
    
    def get_typed_value(self):
        """
        Retorna o valor da configuração convertido para o tipo apropriado.
        
        Returns:
            Valor convertido para o tipo especificado em config_type
        """
        if self.config_type == "float":
            return float(self.config_value)
        elif self.config_type == "int":
            return int(self.config_value)
        elif self.config_type == "bool":
            return self.config_value.lower() in ("true", "1", "yes")
        elif self.config_type == "json":
            import json
            return json.loads(self.config_value)
        else:
            return self.config_value
    
    def __repr__(self):
        return f"<GlobalConfig(id={self.id}, key={self.config_key}, value={self.config_value})>"
