"""
Test suite for FlexFlow Workflow Service
Tests state machine transitions, validations, and audit trail integrity.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock

from backend.database import Base
from backend.models import (
    PurchaseOrder,
    POItem,
    POAttachment,
    POStatus,
    AuditLog
)
from backend.services.workflow_service import WorkflowService, WorkflowTransitionError
from backend.services.validators import StateValidator
from backend.middleware import RequestContext
from backend.security import TokenPayload


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_context():
    """Create a test request context"""
    token_payload = Mock(spec=TokenPayload)
    token_payload.user_id = "test_user_123"
    token_payload.tenant_id = "test_tenant_456"
    token_payload.email = "test@promaflex.com"
    token_payload.permissions = [
        "po.create",
        "po.read",
        "po.approve_comercial",
        "po.approve_pcp",
        "po.reject_pcp",
        "po.approve_producao",
        "po.complete_expedicao",
        "po.complete_faturamento",
        "po.approve_despacho"
    ]
    token_payload.role = "admin"
    
    context = RequestContext(
        tenant_id="test_tenant_456",
        user_id="test_user_123",
        token_payload=token_payload,
        ip_address="192.168.1.100"
    )
    return context


@pytest.fixture
def sample_po(db_session, test_context):
    """Create a sample Purchase Order"""
    po = PurchaseOrder(
        tenant_id=test_context.tenant_id,
        po_number="PO-2024-001",
        customer_name="Test Customer",
        customer_contact="customer@test.com",
        delivery_date=(datetime.utcnow() + timedelta(days=30)).date(),
        status=POStatus.COMERCIAL,
        created_by=test_context.user_id
    )
    
    # Add items
    item1 = POItem(
        tenant_id=test_context.tenant_id,
        description="Standard Widget",
        quantity=10,
        unit_price=100.00,
        is_personalized=False
    )
    item2 = POItem(
        tenant_id=test_context.tenant_id,
        description="Custom Widget",
        quantity=5,
        unit_price=200.00,
        is_personalized=True
    )
    
    po.items = [item1, item2]
    
    db_session.add(po)
    db_session.commit()
    db_session.refresh(po)
    
    return po


class TestStateValidators:
    """Test state validation logic"""
    
    def test_validate_comercial_to_pcp_success(self, db_session, sample_po):
        """Test successful COMERCIAL to PCP validation"""
        result = StateValidator.validate_comercial_to_pcp(sample_po, db_session)
        assert result.is_valid
        assert "Ready for PCP review" in result.message
    
    def test_validate_comercial_to_pcp_no_items(self, db_session, test_context):
        """Test COMERCIAL to PCP validation fails without items"""
        po = PurchaseOrder(
            tenant_id=test_context.tenant_id,
            po_number="PO-2024-002",
            customer_name="Test Customer",
            customer_contact="customer@test.com",
            delivery_date=(datetime.utcnow() + timedelta(days=30)).date(),
            status=POStatus.COMERCIAL,
            created_by=test_context.user_id
        )
        db_session.add(po)
        db_session.commit()
        
        result = StateValidator.validate_comercial_to_pcp(po, db_session)
        assert not result.is_valid
        assert result.error_code == "NO_ITEMS"
    
    def test_validate_pcp_to_producao_missing_attachments(self, db_session, sample_po):
        """Test PCP to PRODUCAO validation fails for personalized items without attachments"""
        sample_po.production_schedule_date = (datetime.utcnow() + timedelta(days=7)).date()
        db_session.commit()
        
        result = StateValidator.validate_pcp_to_producao(sample_po, db_session)
        assert not result.is_valid
        assert result.error_code == "MISSING_PERSONALIZED_ATTACHMENTS"
        assert "Custom Widget" in result.message
    
    def test_validate_pcp_to_producao_with_attachments(self, db_session, sample_po):
        """Test PCP to PRODUCAO validation succeeds with attachments"""
        sample_po.production_schedule_date = (datetime.utcnow() + timedelta(days=7)).date()
        
        # Add attachment for personalized item
        attachment = POAttachment(
            tenant_id=sample_po.tenant_id,
            file_name="technical_drawing.pdf",
            file_path="/uploads/technical_drawing.pdf",
            file_type="technical_drawing",
            uploaded_by=sample_po.created_by
        )
        sample_po.attachments = [attachment]
        db_session.commit()
        
        result = StateValidator.validate_pcp_to_producao(sample_po, db_session)
        assert result.is_valid
        assert "Ready for production" in result.message


class TestWorkflowService:
    """Test workflow service state transitions"""
    
    @pytest.mark.asyncio
    async def test_approve_comercial(self, db_session, sample_po, test_context):
        """Test approving COMERCIAL and transitioning to PCP"""
        workflow = WorkflowService(db_session)
        
        updated_po = await workflow.approve_comercial(
            po_id=sample_po.id,
            context=test_context
        )
        
        assert updated_po.status == POStatus.PCP
        
        # Check audit log was created
        audit_logs = db_session.query(AuditLog).filter(
            AuditLog.entity_id == sample_po.id
        ).all()
        assert len(audit_logs) == 1
        assert audit_logs[0].action == "state_transition"
        assert audit_logs[0].changes["status"]["from"] == POStatus.COMERCIAL.value
        assert audit_logs[0].changes["status"]["to"] == POStatus.PCP.value
    
    @pytest.mark.asyncio
    async def test_approve_pcp_without_attachments_fails(self, db_session, sample_po, test_context):
        """Test PCP approval fails for personalized items without attachments"""
        # First transition to PCP
        sample_po.status = POStatus.PCP
        sample_po.production_schedule_date = (datetime.utcnow() + timedelta(days=7)).date()
        db_session.commit()
        
        workflow = WorkflowService(db_session)
        
        with pytest.raises(WorkflowTransitionError) as exc_info:
            await workflow.approve_pcp(
                po_id=sample_po.id,
                context=test_context
            )
        
        assert exc_info.value.error_code == "MISSING_PERSONALIZED_ATTACHMENTS"
    
    @pytest.mark.asyncio
    async def test_reject_pcp_returns_to_comercial(self, db_session, sample_po, test_context):
        """Test PCP rejection returns to COMERCIAL"""
        # First transition to PCP
        sample_po.status = POStatus.PCP
        db_session.commit()
        
        workflow = WorkflowService(db_session)
        
        updated_po = await workflow.reject_pcp(
            po_id=sample_po.id,
            context=test_context,
            reason="Missing customer specifications"
        )
        
        assert updated_po.status == POStatus.COMERCIAL
        
        # Check audit log
        audit_logs = db_session.query(AuditLog).filter(
            AuditLog.entity_id == sample_po.id
        ).order_by(AuditLog.created_at.desc()).all()
        assert len(audit_logs) >= 1
        assert "PCP Rejection" in audit_logs[0].metadata["reason"]
    
    @pytest.mark.asyncio
    async def test_parallel_states_workflow(self, db_session, sample_po, test_context):
        """Test parallel states (EXPEDICAO + FATURAMENTO) workflow"""
        # Setup: Move to PRODUCAO state
        sample_po.status = POStatus.PRODUCAO
        sample_po.production_schedule_date = (datetime.utcnow() + timedelta(days=7)).date()
        sample_po.quality_check_passed = True
        sample_po.production_notes = "Production completed successfully"
        
        # Mark all items as produced
        for item in sample_po.items:
            item.production_completed = True
        
        db_session.commit()
        
        workflow = WorkflowService(db_session)
        
        # Approve production - should transition to parallel states
        updated_po = await workflow.approve_producao(
            po_id=sample_po.id,
            context=test_context
        )
        
        assert updated_po.status == POStatus.EXPEDICAO_PENDENTE
        assert not updated_po.expedicao_completed
        assert not updated_po.faturamento_completed
    
    @pytest.mark.asyncio
    async def test_complete_parallel_states_transitions_to_despacho(
        self, db_session, sample_po, test_context
    ):
        """Test completing both parallel states transitions to DESPACHO"""
        # Setup: Move to parallel states
        sample_po.status = POStatus.EXPEDICAO_PENDENTE
        sample_po.expedicao_completed = False
        sample_po.faturamento_completed = False
        sample_po.packing_list_generated = True
        sample_po.shipping_docs_complete = True
        sample_po.payment_terms_confirmed = True
        
        # Add invoice attachment
        invoice = POAttachment(
            tenant_id=sample_po.tenant_id,
            file_name="invoice.pdf",
            file_path="/uploads/invoice.pdf",
            file_type="invoice",
            uploaded_by=test_context.user_id
        )
        sample_po.attachments = [invoice]
        db_session.commit()
        
        workflow = WorkflowService(db_session)
        
        # Complete expedicao
        updated_po = await workflow.complete_expedicao(
            po_id=sample_po.id,
            context=test_context
        )
        assert updated_po.expedicao_completed
        assert updated_po.status == POStatus.EXPEDICAO_PENDENTE  # Still in parallel state
        
        # Complete faturamento - should transition to DESPACHO
        updated_po = await workflow.complete_faturamento(
            po_id=sample_po.id,
            context=test_context
        )
        assert updated_po.faturamento_completed
        assert updated_po.status == POStatus.DESPACHO


class TestAuditTrail:
    """Test audit trail and hash chaining"""
    
    @pytest.mark.asyncio
    async def test_audit_hash_chaining(self, db_session, sample_po, test_context):
        """Test that audit logs are properly chained with SHA-256 hashes"""
        workflow = WorkflowService(db_session)
        
        # Perform multiple transitions
        await workflow.approve_comercial(sample_po.id, test_context)
        
        # Get audit logs
        audit_logs = db_session.query(AuditLog).filter(
            AuditLog.entity_id == sample_po.id
        ).order_by(AuditLog.created_at.asc()).all()
        
        assert len(audit_logs) >= 1
        
        # First log should have "genesis" as previous hash
        assert audit_logs[0].previous_hash == "genesis"
        assert audit_logs[0].current_hash is not None
        assert len(audit_logs[0].current_hash) == 64  # SHA-256 produces 64 hex characters
    
    @pytest.mark.asyncio
    async def test_verify_audit_chain_integrity(self, db_session, sample_po, test_context):
        """Test audit chain verification"""
        workflow = WorkflowService(db_session)
        
        # Perform transitions
        await workflow.approve_comercial(sample_po.id, test_context)
        
        # Verify chain
        verification = workflow.verify_audit_chain(sample_po.id, test_context.tenant_id)
        
        assert verification["is_valid"]
        assert verification["total_records"] >= 1
        assert verification["verified_records"] == verification["total_records"]
        assert verification["broken_at"] is None
    
    @pytest.mark.asyncio
    async def test_workflow_history(self, db_session, sample_po, test_context):
        """Test retrieving workflow history"""
        workflow = WorkflowService(db_session)
        
        # Perform transitions
        await workflow.approve_comercial(sample_po.id, test_context)
        
        # Get history
        history = workflow.get_workflow_history(sample_po.id, test_context.tenant_id)
        
        assert len(history) >= 1
        assert history[0]["from_status"] == POStatus.COMERCIAL.value
        assert history[0]["to_status"] == POStatus.PCP.value
        assert history[0]["user_id"] == test_context.user_id
        assert history[0]["ip_address"] == test_context.ip_address


class TestPermissionValidation:
    """Test permission-based authorization"""
    
    def test_context_has_permission(self, test_context):
        """Test permission checking in context"""
        assert test_context.has_permission("po.create")
        assert test_context.has_permission("po.approve_comercial")
        assert not test_context.has_permission("po.delete")
    
    def test_context_has_any_permission(self, test_context):
        """Test any permission checking"""
        assert test_context.has_any_permission(["po.create", "po.delete"])
        assert not test_context.has_any_permission(["po.delete", "admin.access"])
    
    def test_context_has_all_permissions(self, test_context):
        """Test all permissions checking"""
        assert test_context.has_all_permissions(["po.create", "po.read"])
        assert not test_context.has_all_permissions(["po.create", "po.delete"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
