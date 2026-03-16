"""
Base repository with automatic tenant isolation.

This module provides a generic repository class that automatically filters
all queries by tenant_id, ensuring data isolation between tenants.
"""

from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_
from backend.models import Base

# Generic type for model classes
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository with automatic tenant filtering.
    
    This class provides CRUD operations with automatic tenant_id filtering
    to ensure data isolation. All queries are automatically scoped to the
    specified tenant.
    
    Attributes:
        model: The SQLAlchemy model class this repository manages
        db: The database session
        tenant_id: The UUID of the current tenant for filtering
    """
    
    def __init__(self, model: Type[ModelType], db: Session, tenant_id: UUID):
        """
        Initialize the repository.
        
        Args:
            model: SQLAlchemy model class
            db: Database session
            tenant_id: UUID of the tenant for filtering operations
        """
        self.model = model
        self.db = db
        self.tenant_id = tenant_id
    
    def _apply_tenant_filter(self, query):
        """
        Apply tenant_id filter to a query.
        
        Args:
            query: SQLAlchemy query object
            
        Returns:
            Query with tenant_id filter applied
        """
        return query.filter(self.model.tenant_id == self.tenant_id)
    
    def create(self, obj: ModelType) -> ModelType:
        """
        Create a new record with automatic tenant_id assignment.
        
        Args:
            obj: Model instance to create
            
        Returns:
            Created model instance with assigned ID
        """
        # Ensure tenant_id is set
        obj.tenant_id = self.tenant_id
        
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj
    
    def get_by_id(self, id: UUID) -> Optional[ModelType]:
        """
        Get a single record by ID, filtered by tenant.
        
        Args:
            id: UUID of the record
            
        Returns:
            Model instance if found, None otherwise
        """
        query = self.db.query(self.model).filter(self.model.id == id)
        return self._apply_tenant_filter(query).first()
    
    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """
        Get all records for the tenant with optional filtering and pagination.
        
        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            filters: Optional dictionary of field:value filters
            
        Returns:
            List of model instances
        """
        query = self.db.query(self.model)
        query = self._apply_tenant_filter(query)
        
        # Apply additional filters if provided
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.filter(getattr(self.model, field) == value)
        
        return query.offset(skip).limit(limit).all()
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records for the tenant with optional filtering.
        
        Args:
            filters: Optional dictionary of field:value filters
            
        Returns:
            Number of records matching the criteria
        """
        query = self.db.query(self.model)
        query = self._apply_tenant_filter(query)
        
        # Apply additional filters if provided
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.filter(getattr(self.model, field) == value)
        
        return query.count()
    
    def update(self, id: UUID, data: Dict[str, Any]) -> Optional[ModelType]:
        """
        Update a record by ID, filtered by tenant.
        
        Args:
            id: UUID of the record to update
            data: Dictionary of fields to update
            
        Returns:
            Updated model instance if found, None otherwise
        """
        obj = self.get_by_id(id)
        if not obj:
            return None
        
        # Update fields
        for field, value in data.items():
            if hasattr(obj, field) and field != "id" and field != "tenant_id":
                setattr(obj, field, value)
        
        self.db.commit()
        self.db.refresh(obj)
        return obj
    
    def delete(self, id: UUID) -> bool:
        """
        Delete a record by ID, filtered by tenant.
        
        Args:
            id: UUID of the record to delete
            
        Returns:
            True if deleted, False if not found
        """
        obj = self.get_by_id(id)
        if not obj:
            return False
        
        self.db.delete(obj)
        self.db.commit()
        return True
    
    def exists(self, id: UUID) -> bool:
        """
        Check if a record exists by ID, filtered by tenant.
        
        Args:
            id: UUID of the record
            
        Returns:
            True if exists, False otherwise
        """
        query = self.db.query(self.model.id).filter(self.model.id == id)
        return self._apply_tenant_filter(query).first() is not None
    
    def bulk_create(self, objects: List[ModelType]) -> List[ModelType]:
        """
        Create multiple records with automatic tenant_id assignment.
        
        Args:
            objects: List of model instances to create
            
        Returns:
            List of created model instances
        """
        # Ensure tenant_id is set for all objects
        for obj in objects:
            obj.tenant_id = self.tenant_id
        
        self.db.add_all(objects)
        self.db.commit()
        
        # Refresh all objects
        for obj in objects:
            self.db.refresh(obj)
        
        return objects
    
    def get_by_field(self, field: str, value: Any) -> Optional[ModelType]:
        """
        Get a single record by a specific field value, filtered by tenant.
        
        Args:
            field: Name of the field to filter by
            value: Value to match
            
        Returns:
            Model instance if found, None otherwise
        """
        if not hasattr(self.model, field):
            return None
        
        query = self.db.query(self.model).filter(getattr(self.model, field) == value)
        return self._apply_tenant_filter(query).first()
    
    def get_many_by_field(
        self,
        field: str,
        value: Any,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """
        Get multiple records by a specific field value, filtered by tenant.
        
        Args:
            field: Name of the field to filter by
            value: Value to match
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of model instances
        """
        if not hasattr(self.model, field):
            return []
        
        query = self.db.query(self.model).filter(getattr(self.model, field) == value)
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
