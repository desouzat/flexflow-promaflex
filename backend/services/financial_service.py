"""
FlexFlow Financial Service
Handles commission ladder logic, VP (Present Value) calculations, and financial metrics.
"""

from decimal import Decimal
from typing import Dict, Optional, Tuple
from datetime import datetime
import math


class FinancialService:
    """
    Service for financial calculations including:
    - Commission ladder based on margin
    - Present Value (VP) calculations with variable rates
    - CSN exception handling
    """
    
    # Commission Ladder Configuration
    COMMISSION_LADDER = [
        {"min_margin": 0.00, "max_margin": 18.99, "commission": 0.00, "alert": True},
        {"min_margin": 19.00, "max_margin": 24.99, "commission": 2.00},
        {"min_margin": 25.00, "max_margin": 29.99, "commission": 2.25},
        {"min_margin": 30.00, "max_margin": 39.99, "commission": 2.50},
        {"min_margin": 40.00, "max_margin": 44.99, "commission": 3.50},
        {"min_margin": 45.00, "max_margin": 49.99, "commission": 4.00},
        {"min_margin": 50.00, "max_margin": 999.99, "commission": 4.50},
    ]
    
    # CSN Exception
    CSN_CLIENT_CODE = "CSN"
    CSN_COMMISSION_RATE = 1.5
    
    # VP (Present Value) Rates per Term (in days)
    VP_RATES = {
        30: 0.0150,   # 1.50% for 30 days
        60: 0.0300,   # 3.00% for 60 days
        90: 0.0450,   # 4.50% for 90 days
        120: 0.0600,  # 6.00% for 120 days
    }
    
    @classmethod
    def calculate_margin(
        cls,
        sale_price: Decimal,
        cost: Decimal,
        shipping_cost: Decimal = Decimal("0.00"),
        tax_rate: Decimal = Decimal("22.25")
    ) -> Decimal:
        """
        Calculate margin percentage.
        
        Formula: Margin = ((Sale Price - Cost - Shipping - Taxes) / Sale Price) * 100
        
        Args:
            sale_price: Sale price of the item/PO
            cost: Total cost (material cost)
            shipping_cost: Shipping/freight cost
            tax_rate: Tax rate percentage (default 22.25%)
            
        Returns:
            Margin percentage
        """
        if sale_price <= 0:
            return Decimal("0.00")
        
        # Calculate taxes
        taxes = sale_price * (tax_rate / Decimal("100"))
        
        # Calculate margin
        margin = ((sale_price - cost - shipping_cost - taxes) / sale_price) * Decimal("100")
        
        return margin.quantize(Decimal("0.01"))
    
    @classmethod
    def get_commission_rate(
        cls,
        margin: Decimal,
        client_code: Optional[str] = None,
        manual_override: Optional[Decimal] = None
    ) -> Tuple[Decimal, bool, str]:
        """
        Get commission rate based on margin and client.
        
        Args:
            margin: Margin percentage
            client_code: Client code (e.g., 'CSN')
            manual_override: Manual commission rate set by MASTER user
            
        Returns:
            Tuple of (commission_rate, has_alert, reason)
        """
        # Priority 1: Manual override by MASTER
        if manual_override is not None:
            return (manual_override, False, "Manual Override by MASTER")
        
        # Priority 2: CSN Exception
        if client_code and client_code.upper() == cls.CSN_CLIENT_CODE:
            return (Decimal(str(cls.CSN_COMMISSION_RATE)), False, "CSN Fixed Rate")
        
        # Priority 3: Commission Ladder
        for bracket in cls.COMMISSION_LADDER:
            if bracket["min_margin"] <= margin <= bracket["max_margin"]:
                has_alert = bracket.get("alert", False)
                reason = "Low Margin Alert" if has_alert else "Standard Ladder"
                return (Decimal(str(bracket["commission"])), has_alert, reason)
        
        # Fallback (should not happen with proper ladder config)
        return (Decimal("0.00"), True, "Margin out of range")
    
    @classmethod
    def calculate_commission_value(
        cls,
        sale_price: Decimal,
        commission_rate: Decimal
    ) -> Decimal:
        """
        Calculate commission value.
        
        Args:
            sale_price: Sale price
            commission_rate: Commission rate percentage
            
        Returns:
            Commission value in currency
        """
        commission = sale_price * (commission_rate / Decimal("100"))
        return commission.quantize(Decimal("0.01"))
    
    @classmethod
    def calculate_vp(
        cls,
        future_value: Decimal,
        term_days: int,
        custom_rate: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate Present Value (VP - Valor Presente).
        
        Formula: VP = FV / (1 + rate)
        
        Args:
            future_value: Future value (sale price)
            term_days: Payment term in days
            custom_rate: Custom discount rate (optional)
            
        Returns:
            Present value
        """
        if future_value <= 0:
            return Decimal("0.00")
        
        # Get rate for the term
        if custom_rate is not None:
            rate = custom_rate
        else:
            # Find closest term or interpolate
            rate = cls._get_vp_rate_for_term(term_days)
        
        # Calculate VP
        vp = future_value / (Decimal("1") + rate)
        return vp.quantize(Decimal("0.01"))
    
    @classmethod
    def _get_vp_rate_for_term(cls, term_days: int) -> Decimal:
        """
        Get VP rate for a given term, with interpolation for non-standard terms.
        
        Args:
            term_days: Payment term in days
            
        Returns:
            VP rate as decimal
        """
        # Exact match
        if term_days in cls.VP_RATES:
            return Decimal(str(cls.VP_RATES[term_days]))
        
        # Interpolation for terms between standard values
        sorted_terms = sorted(cls.VP_RATES.keys())
        
        # Below minimum
        if term_days < sorted_terms[0]:
            # Linear interpolation from 0
            rate = (term_days / sorted_terms[0]) * cls.VP_RATES[sorted_terms[0]]
            return Decimal(str(rate))
        
        # Above maximum
        if term_days > sorted_terms[-1]:
            # Linear extrapolation
            rate = (term_days / sorted_terms[-1]) * cls.VP_RATES[sorted_terms[-1]]
            return Decimal(str(rate))
        
        # Between two standard terms
        for i in range(len(sorted_terms) - 1):
            lower_term = sorted_terms[i]
            upper_term = sorted_terms[i + 1]
            
            if lower_term < term_days < upper_term:
                lower_rate = cls.VP_RATES[lower_term]
                upper_rate = cls.VP_RATES[upper_term]
                
                # Linear interpolation
                ratio = (term_days - lower_term) / (upper_term - lower_term)
                rate = lower_rate + (upper_rate - lower_rate) * ratio
                return Decimal(str(rate))
        
        # Fallback
        return Decimal("0.00")
    
    @classmethod
    def calculate_po_financials(
        cls,
        sale_price: Decimal,
        cost: Decimal,
        shipping_cost: Decimal,
        term_days: int,
        client_code: Optional[str] = None,
        manual_commission_rate: Optional[Decimal] = None,
        tax_rate: Decimal = Decimal("22.25")
    ) -> Dict:
        """
        Calculate all financial metrics for a PO.
        
        Args:
            sale_price: Total sale price
            cost: Total cost
            shipping_cost: Shipping cost
            term_days: Payment term in days
            client_code: Client code
            manual_commission_rate: Manual commission override
            tax_rate: Tax rate percentage
            
        Returns:
            Dictionary with all financial metrics
        """
        # Calculate margin
        margin = cls.calculate_margin(sale_price, cost, shipping_cost, tax_rate)
        
        # Get commission rate
        commission_rate, has_alert, commission_reason = cls.get_commission_rate(
            margin, client_code, manual_commission_rate
        )
        
        # Calculate commission value
        commission_value = cls.calculate_commission_value(sale_price, commission_rate)
        
        # Calculate VP
        vp = cls.calculate_vp(sale_price, term_days)
        
        # Calculate VP discount
        vp_discount = sale_price - vp
        
        # Calculate net profit
        taxes = sale_price * (tax_rate / Decimal("100"))
        net_profit = sale_price - cost - shipping_cost - taxes - commission_value
        
        return {
            "sale_price": float(sale_price),
            "cost": float(cost),
            "shipping_cost": float(shipping_cost),
            "tax_rate": float(tax_rate),
            "taxes": float(taxes),
            "margin_percent": float(margin),
            "commission_rate": float(commission_rate),
            "commission_value": float(commission_value),
            "commission_reason": commission_reason,
            "has_margin_alert": has_alert,
            "vp": float(vp),
            "vp_discount": float(vp_discount),
            "term_days": term_days,
            "net_profit": float(net_profit),
            "client_code": client_code,
        }
    
    @classmethod
    def verify_split_consistency(
        cls,
        mother_financials: Dict,
        child_financials_list: list[Dict]
    ) -> Dict:
        """
        Verify mathematical consistency between mother PO and child POs after split.
        
        Args:
            mother_financials: Financial metrics of mother PO
            child_financials_list: List of financial metrics for each child PO
            
        Returns:
            Dictionary with verification results
        """
        # Sum child values
        total_child_sale = sum(c["sale_price"] for c in child_financials_list)
        total_child_cost = sum(c["cost"] for c in child_financials_list)
        total_child_shipping = sum(c["shipping_cost"] for c in child_financials_list)
        total_child_commission = sum(c["commission_value"] for c in child_financials_list)
        
        # Calculate differences
        sale_diff = abs(mother_financials["sale_price"] - total_child_sale)
        cost_diff = abs(mother_financials["cost"] - total_child_cost)
        shipping_diff = abs(mother_financials["shipping_cost"] - total_child_shipping)
        
        # Tolerance for floating point comparison (0.01 = 1 cent)
        tolerance = 0.01
        
        is_consistent = (
            sale_diff < tolerance and
            cost_diff < tolerance and
            shipping_diff < tolerance
        )
        
        return {
            "is_consistent": is_consistent,
            "mother_sale_price": mother_financials["sale_price"],
            "total_child_sale_price": total_child_sale,
            "sale_difference": sale_diff,
            "mother_cost": mother_financials["cost"],
            "total_child_cost": total_child_cost,
            "cost_difference": cost_diff,
            "mother_shipping": mother_financials["shipping_cost"],
            "total_child_shipping": total_child_shipping,
            "shipping_difference": shipping_diff,
            "mother_commission": mother_financials["commission_value"],
            "total_child_commission": total_child_commission,
            "commission_note": "Commissions may differ due to different margins after split",
        }
