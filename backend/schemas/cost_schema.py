"""
FlexFlow Cost Management Schemas
Schemas para gerenciamento de custos de materiais (MASTER only)
"""

from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from decimal import Decimal
import uuid


class MaterialCostBase(BaseModel):
    """Schema base para custos de material"""
    sku: str = Field(..., min_length=1, max_length=100, description="SKU do material")
    nome: str = Field(..., min_length=1, max_length=255, description="Nome do material")
    custo_mp_kg: Decimal = Field(..., ge=0, description="Custo de matéria-prima por kg")
    rendimento: Decimal = Field(..., gt=0, description="Rendimento em kg por unidade")
    indice_impostos: Decimal = Field(
        default=Decimal("22.25"),
        ge=0,
        le=100,
        description="Índice de impostos em percentual"
    )


class MaterialCostCreate(MaterialCostBase):
    """Schema para criação de custo de material"""
    pass


class MaterialCostUpdate(BaseModel):
    """Schema para atualização de custo de material"""
    nome: Optional[str] = Field(None, min_length=1, max_length=255)
    custo_mp_kg: Optional[Decimal] = Field(None, ge=0)
    rendimento: Optional[Decimal] = Field(None, gt=0)
    indice_impostos: Optional[Decimal] = Field(None, ge=0, le=100)


class MaterialCostResponse(MaterialCostBase):
    """Schema de resposta para custo de material"""
    id: str
    tenant_id: str
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str] = None

    class Config:
        from_attributes = True


class MaterialCostListResponse(BaseModel):
    """Schema de resposta para lista de custos"""
    items: list[MaterialCostResponse]
    total: int
    skip: int
    limit: int


class GlobalSettingsResponse(BaseModel):
    """Schema para configurações globais de custos"""
    indice_impostos_padrao: Decimal = Field(
        default=Decimal("22.25"),
        description="Índice de impostos padrão em percentual"
    )
    tenant_id: str


class GlobalSettingsUpdate(BaseModel):
    """Schema para atualização de configurações globais"""
    indice_impostos_padrao: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Índice de impostos padrão em percentual"
    )
