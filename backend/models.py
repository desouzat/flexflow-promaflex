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
    ForeignKey, CheckConstraint, Index, Text, JSON, Enum, UUID
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.ext.compiler import compiles

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(32)"

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

try:
    from backend.database import Base
except ModuleNotFoundError:
    from database import Base


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
    support_tickets: Mapped[List["SupportTicket"]] = relationship(
        "SupportTicket",
        back_populates="user",
        cascade="all, delete-orphan"
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
    
    # Status macro permitidos (aligned with column names)
    STATUS_DRAFT = "DRAFT"  # Comercial
    STATUS_SUBMITTED = "SUBMITTED"  # Comercial (New constant default)
    STATUS_APPROVED = "APPROVED"  # PCP
    STATUS_MANUFACTURING = "MANUFACTURING"  # Produção
    STATUS_SHIPPING = "SHIPPING"  # Expedição
    STATUS_FINANCE = "FINANCE"  # Financeiro
    STATUS_COMPLETED = "COMPLETED"  # Concluído
    STATUS_CANCELLED = "CANCELLED"
    STATUS_WAITING_COMMERCIAL_PARTITION = "WAITING_COMMERCIAL_PARTITION"
    STATUS_ANALISE_CREDITO = "ANALISE_CREDITO"
    STATUS_ARCHIVED = "ARCHIVED"
    STATUS_ARCHIVED_PARTITIONED = "ARCHIVED_PARTITIONED"
    STATUS_WAITING_MATERIAL = "WAITING_MATERIAL"
    
    VALID_STATUSES = [
        STATUS_DRAFT, STATUS_SUBMITTED, STATUS_APPROVED,
        STATUS_MANUFACTURING, STATUS_SHIPPING, STATUS_FINANCE,
        STATUS_COMPLETED, STATUS_CANCELLED,
        STATUS_WAITING_COMMERCIAL_PARTITION, STATUS_ANALISE_CREDITO,
        STATUS_ARCHIVED, STATUS_ARCHIVED_PARTITIONED, STATUS_WAITING_MATERIAL
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
    
    # Partition fields
    parent_po_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to parent PO if this is a child from partition"
    )
    partition_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for partition suggested by PCP"
    )
    shipping_cost: Mapped[float] = mapped_column(
        Numeric(10, 2),
        default=0.00,
        nullable=False,
        comment="Shipping cost for this PO (used in partition recalculation)"
    )
    is_partitioned: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Flag indicating if this PO has been partitioned"
    )
    partition_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Metadata about partition: original_items, split_date, freight_strategy, etc."
    )
    
    # SLA pause fields
    sla_paused_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when SLA timer was paused"
    )
    total_hold_time_seconds: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Accumulated pause time in seconds for SLA freeze"
    )
    
    # Financial fields (22-field ONET structure)
    po_total_value: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="PO total value from ONET (Valor Total do Pedido)"
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
    parent_po: Mapped[Optional["PurchaseOrder"]] = relationship(
        "PurchaseOrder",
        remote_side="PurchaseOrder.id",
        foreign_keys=[parent_po_id],
        backref="child_pos"
    )
    
    # Índices e Constraints
    __table_args__ = (
        Index('idx_po_tenant_id', 'tenant_id'),
        Index('idx_po_tenant_po_number', 'tenant_id', 'po_number', unique=True),
        Index('idx_po_status_macro', 'status_macro'),
        Index('idx_po_created_by', 'created_by'),
        Index('idx_po_parent_po_id', 'parent_po_id'),
        Index('idx_po_is_partitioned', 'is_partitioned'),
        CheckConstraint(
            f"status_macro IN {tuple(VALID_STATUSES)}",
            name='check_po_status_macro'
        ),
    )
    
    @property
    def client_name(self) -> str:
        """
        Getter para client_name. Retorna o nome do cliente armazenado em partition_metadata
        ou recupera o valor correspondente nos itens.
        """
        if self.partition_metadata and "client_name" in self.partition_metadata:
            return self.partition_metadata["client_name"]
        
        # Fallback para os itens associados
        if self.items:
            for item in self.items:
                if item.extra_metadata and "client_name" in item.extra_metadata:
                    return item.extra_metadata["client_name"]
                    
        return "Cliente Desconhecido"

    @client_name.setter
    def client_name(self, value: str):
        """
        Setter para client_name. Armazena o valor em partition_metadata.
        """
        if self.partition_metadata is None:
            self.partition_metadata = {}
        self.partition_metadata["client_name"] = value

    @property
    def expected_delivery_date(self) -> Optional[datetime]:
        """
        Getter para expected_delivery_date. Retorna a data armazenada em partition_metadata
        ou recupera a data nos itens.
        """
        from datetime import date
        if self.partition_metadata and "expected_delivery_date" in self.partition_metadata:
            val = self.partition_metadata["expected_delivery_date"]
            if val:
                if isinstance(val, datetime):
                    return val
                if isinstance(val, date):
                    return datetime(val.year, val.month, val.day)
                try:
                    return datetime.fromisoformat(str(val))
                except ValueError:
                    try:
                        return datetime.strptime(str(val), "%Y-%m-%d")
                    except ValueError:
                        try:
                            if "/" in str(val):
                                parts = str(val).split("/")
                                if len(parts) == 3:
                                    d, m, y = parts
                                    return datetime(int(y), int(m), int(d))
                        except ValueError:
                            pass
                    return None
        
        # Fallback para os itens associados
        if self.items:
            for item in self.items:
                if item.extra_metadata:
                    for key in ["expected_delivery_date", "delivery_date", "data_previsao_entrega", "Previsão de Entrega"]:
                        if key in item.extra_metadata and item.extra_metadata[key]:
                            val = item.extra_metadata[key]
                            if isinstance(val, datetime):
                                return val
                            if isinstance(val, date):
                                return datetime(val.year, val.month, val.day)
                            try:
                                return datetime.fromisoformat(str(val))
                            except ValueError:
                                try:
                                    return datetime.strptime(str(val), "%Y-%m-%d")
                                except ValueError:
                                    try:
                                        if "/" in str(val):
                                            parts = str(val).split("/")
                                            if len(parts) == 3:
                                                d, m, y = parts
                                                return datetime(int(y), int(m), int(d))
                                    except ValueError:
                                        pass
                                
        return None

    @expected_delivery_date.setter
    def expected_delivery_date(self, value):
        """
        Setter para expected_delivery_date. Armazena o valor em partition_metadata.
        """
        from datetime import date
        if self.partition_metadata is None:
            self.partition_metadata = {}
        
        if isinstance(value, (datetime, date)):
            self.partition_metadata["expected_delivery_date"] = value.isoformat()
        else:
            self.partition_metadata["expected_delivery_date"] = value

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
    STATUS_ANALISE_CREDITO = "ANALISE_CREDITO"
    STATUS_FINANCE_APPROVED = "FINANCE_APPROVED"
    STATUS_FINANCE_REJECTED = "FINANCE_REJECTED"
    
    VALID_STATUSES = [
        STATUS_PENDING, STATUS_ORDERED, STATUS_RECEIVED,
        STATUS_QUALITY_CHECK, STATUS_APPROVED, STATUS_REJECTED, STATUS_CANCELLED,
        STATUS_ANALISE_CREDITO, STATUS_FINANCE_APPROVED, STATUS_FINANCE_REJECTED
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
    
    # Financial fields (22-field ONET structure)
    unit_value: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Unit value from ONET (Vl.Unit)"
    )
    item_total_value: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Item total value from ONET (Total Item = Qtd × Vl.Unit)"
    )
    
    # Staging Area / Customization fields
    is_personalized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_new_client: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    customization_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachment_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Partition tracking fields
    partition_group: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Partition group identifier (e.g., 'SHIP_NOW', 'SHIP_LATER')"
    )
    original_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to original item if this is from a partition"
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

    # ─── Hash versioning ───────────────────────────────────────────────────────
    # Version 1 (legacy): hash = SHA256(item_id + statuses + timestamp + prev_hash + user)
    # Version 2 (current): hash = SHA256(tenant_id + item_id + statuses + timestamp + prev_hash + user)
    # tenant_id was added in v2 to prevent cross-tenant hash collision attacks.
    # Existing records (hash_version=1) remain valid and are NOT re-hashed.
    HASH_VERSION_LEGACY = 1
    HASH_VERSION_CURRENT = 2

    hash_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=HASH_VERSION_CURRENT,
        comment="Hash algorithm version: 1=legacy (no tenant_id), 2=includes tenant_id"
    )

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
        Index('idx_audit_hash_version', 'hash_version'),
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
        [V1 — LEGACY] Calcula o hash SHA-256 sem incluir tenant_id.

        This method is preserved for backward compatibility.
        All new records should use calculate_hash_v2().

        Args:
            item_id: ID do item
            from_status: Status anterior
            to_status: Novo status
            timestamp: Timestamp da mudança
            previous_hash: Hash do registro anterior
            changed_by: ID do usuário que fez a mudança

        Returns:
            Hash SHA-256 em formato hexadecimal (64 chars)
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

    @staticmethod
    def calculate_hash_v2(
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        from_status: Optional[str],
        to_status: str,
        timestamp: datetime,
        previous_hash: Optional[str],
        changed_by: Optional[uuid.UUID]
    ) -> str:
        """
        [V2 — CURRENT] Calcula o hash SHA-256 incluindo tenant_id.

        Including tenant_id in the hash prevents a theoretical cross-tenant
        collision attack where records from different tenants could produce
        identical hashes given the same item_id, statuses, and timestamp.

        V2 Hash input order:
            tenant_id + item_id + from_status + to_status + timestamp + previous_hash + changed_by

        Args:
            tenant_id: ID do tenant — binds the hash to this tenant's namespace
            item_id: ID do item
            from_status: Status anterior
            to_status: Novo status
            timestamp: Timestamp da mudança
            previous_hash: Hash do registro anterior (None for genesis records)
            changed_by: ID do usuário que fez a mudança

        Returns:
            Hash SHA-256 em formato hexadecimal (64 chars)
        """
        data = (
            str(tenant_id) +           # V2: tenant_id anchors the hash to this tenant
            str(item_id) +
            (from_status or "") +
            to_status +
            timestamp.isoformat() +
            (previous_hash or "") +
            (str(changed_by) if changed_by else "")
        )
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def calculate_hash_for_version(
        version: int,
        item_id: uuid.UUID,
        from_status: Optional[str],
        to_status: str,
        timestamp: datetime,
        previous_hash: Optional[str],
        changed_by: Optional[uuid.UUID],
        tenant_id: Optional[uuid.UUID] = None
    ) -> str:
        """
        Dispatch to the correct hash function based on version.

        This is the preferred entry point for creating new AuditLog records.
        Always pass tenant_id; it is required for version >= 2.

        Args:
            version: Hash version to use (1=legacy, 2=current)
            tenant_id: Required for version 2. Ignored (but accepted) for version 1.
            ... (other args same as calculate_hash / calculate_hash_v2)

        Returns:
            Hash SHA-256 em formato hexadecimal (64 chars)

        Raises:
            ValueError: If version=2 and tenant_id is None.
            ValueError: If an unknown version is requested.
        """
        if version == AuditLog.HASH_VERSION_LEGACY:
            return AuditLog.calculate_hash(
                item_id=item_id,
                from_status=from_status,
                to_status=to_status,
                timestamp=timestamp,
                previous_hash=previous_hash,
                changed_by=changed_by
            )
        elif version == AuditLog.HASH_VERSION_CURRENT:
            if tenant_id is None:
                raise ValueError(
                    "tenant_id is required for AuditLog hash version 2. "
                    "Pass the tenant's UUID to calculate_hash_for_version()."
                )
            return AuditLog.calculate_hash_v2(
                tenant_id=tenant_id,
                item_id=item_id,
                from_status=from_status,
                to_status=to_status,
                timestamp=timestamp,
                previous_hash=previous_hash,
                changed_by=changed_by
            )
        else:
            raise ValueError(f"Unknown AuditLog hash version: {version}")

    def verify_own_hash(
        self,
        tenant_id: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Verify that this record's stored hash matches a fresh calculation.

        Uses hash_version to select the correct algorithm, so both legacy
        (v1) and current (v2) records can be verified without migration.

        Args:
            tenant_id: Required for v2 records. Ignored for v1 records.

        Returns:
            True if the hash is valid, False if the record has been tampered with.
        """
        try:
            expected = AuditLog.calculate_hash_for_version(
                version=self.hash_version,
                item_id=self.item_id,
                from_status=self.from_status,
                to_status=self.to_status,
                timestamp=self.created_at,
                previous_hash=self.previous_hash,
                changed_by=self.changed_by,
                tenant_id=tenant_id
            )
            return expected == self.hash
        except (ValueError, TypeError):
            return False

    def __repr__(self):
        return (
            f"<AuditLog(id={self.id}, item_id={self.item_id}, "
            f"{self.from_status}->{self.to_status}, v{self.hash_version})>"
        )


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


# ============================================================================
# MODELO: SupportTicket (Sistema de Suporte)
# ============================================================================

class SupportTicket(Base):
    """
    Modelo de Ticket de Suporte.
    Permite que usuários reportem problemas e recebam assistência técnica.
    """
    __tablename__ = "support_tickets"
    
    # Colunas
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default="OPEN",
        nullable=False
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
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Relacionamentos
    user: Mapped["User"] = relationship("User", back_populates="support_tickets")
    
    # Índices e constraints
    __table_args__ = (
        Index('idx_support_ticket_user_id', 'user_id'),
        Index('idx_support_ticket_status', 'status'),
        Index('idx_support_ticket_created_at', 'created_at'),
        CheckConstraint(
            "status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED')",
            name='ck_support_ticket_status'
        ),
    )
    
    def __repr__(self):
        return f"<SupportTicket(id={self.id}, user_id={self.user_id}, status={self.status})>"
