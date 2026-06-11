"""
FlexFlow — Brazilian Number Cleaning Utility
=============================================
Central utility for parsing Brazilian-formatted numbers into standard decimals.

Brazilian number format rules:
  - Thousands separator: dot ('.')      e.g., 13.335 = thirteen thousand three hundred thirty-five
  - Decimal separator:   comma (',')    e.g., 13.335,50 = 13335.50
  - Currency prefix:     'R$' or '$'   e.g., R$ 13.335,00

Usage:
    from backend.utils.number_utils import clean_brazilian_number

    result = clean_brazilian_number("R$ 13.335,00")   # returns "13335.00"
    result = clean_brazilian_number("INVALID")         # returns None
"""

from __future__ import annotations

import math
import re
from typing import Any, Optional

# Pre-compiled patterns for performance
_CURRENCY_PREFIX_RE = re.compile(r'R\$|\$', re.IGNORECASE)
_WHITESPACE_RE = re.compile(r'\s+')


def clean_brazilian_number(value: Any) -> float:
    """
    Normalize a Brazilian currency or number string to a standard float.

    Decision tree:
        1. Reject None, NaN, or non-stringifiable inputs → return 0.0
        2. Strip currency symbols ('R$', '$') and whitespace
        3. If value contains a comma:
               Remove all dots (thousands separators) → replace comma with dot (decimal)
               e.g., "13.335,00" → "13335.00"
        4. If value has no comma but multiple dots:
               Remove all dots (all are thousands separators, no decimals)
               e.g., "13.335.000" → "13335000"
        5. If value has no comma and one dot (or no dot):
               Already in standard format → pass through
               e.g., "13335.00" → "13335.00"
        6. Validate the resulting string is a finite non-negative float
        7. Return the cleaned float, or 0.0 on any failure

    Args:
        value: Input to clean. Can be str, int, float, or Decimal.

    Returns:
        A float (e.g., 13335.00) representing the value, or 0.0 if not valid.

    Examples:
        >>> clean_brazilian_number("R$ 13.335,00")
        13335.0
        >>> clean_brazilian_number("108.753,123456")
        108753.123456
        >>> clean_brazilian_number("INVALID")
        0.0
    """
    if value is None:
        return 0.0

    # Handle native numeric types first
    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return 0.0
        return float(value) if value >= 0.0 else 0.0

    from decimal import Decimal
    if isinstance(value, Decimal):
        try:
            f = float(value)
            if math.isnan(f) or math.isinf(f):
                return 0.0
            return f if f >= 0.0 else 0.0
        except (ValueError, TypeError):
            return 0.0

    # Coerce to string
    try:
        raw = str(value).strip()
    except Exception:
        return 0.0

    if not raw or raw.upper() == "N/A":
        return 0.0

    # Remove currency symbols and whitespace
    cleaned = _CURRENCY_PREFIX_RE.sub('', raw)
    cleaned = _WHITESPACE_RE.sub('', cleaned)
    cleaned = cleaned.strip()

    if not cleaned:
        return 0.0

    # Allow: digits, dot, comma, leading minus
    if not re.match(r'^-?[\d.,]+$', cleaned):
        return 0.0

    # Apply Brazilian format conversion
    has_comma = ',' in cleaned
    dot_count = cleaned.count('.')

    if has_comma:
        # Brazilian format: dots are thousands separators, comma is the decimal separator
        cleaned = cleaned.replace('.', '').replace(',', '.')
    elif dot_count > 1:
        # Multiple dots and no comma: all dots are thousands separators (no decimal part)
        cleaned = cleaned.replace('.', '')

    # Final validation and float conversion
    try:
        numeric = float(cleaned)
        if math.isnan(numeric) or math.isinf(numeric):
            return 0.0
        # Reject negative numbers
        if numeric < 0.0:
            return 0.0
        return numeric
    except (ValueError, TypeError):
        return 0.0

