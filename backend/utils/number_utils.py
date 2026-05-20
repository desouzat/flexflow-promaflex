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


def clean_brazilian_number(value: Any) -> Optional[str]:
    """
    Normalize a Brazilian currency or number string to a standard decimal string.

    Decision tree:
        1. Reject None, NaN, or non-stringifiable inputs → return None
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
        6. Validate the resulting string is a finite non-negative number
        7. Return the cleaned string, or None on any failure

    Args:
        value: Input to clean. Can be str, int, float, or Decimal.

    Returns:
        A standard decimal string (e.g., "13335.00") suitable for Decimal() conversion,
        or None if the value cannot be parsed (including negative numbers).

    Examples:
        >>> clean_brazilian_number("R$ 13.335,00")
        '13335.00'
        >>> clean_brazilian_number("13.335,00")
        '13335.00'
        >>> clean_brazilian_number("1.335,50")
        '1335.50'
        >>> clean_brazilian_number("13335.00")
        '13335.00'
        >>> clean_brazilian_number("13335,00")
        '13335.00'
        >>> clean_brazilian_number("0,50")
        '0.50'
        >>> clean_brazilian_number("INVALID")
        >>> clean_brazilian_number(None)
        >>> clean_brazilian_number(float("nan"))
        >>> clean_brazilian_number(13335.00)
        '13335.0'
    """
    # ── Step 1: Handle None / NaN / non-numeric passthrough ──────────────────
    if value is None:
        return None

    # Handle native float NaN / Inf
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        # Finite float: convert directly to string — Python's str() gives standard notation
        cleaned = str(value)
        # Validate non-negative
        try:
            f = float(cleaned)
            return cleaned if f >= 0 else None
        except ValueError:
            return None

    # Handle int passthrough
    if isinstance(value, int):
        return str(value) if value >= 0 else None

    # ── Step 2: Coerce to string ──────────────────────────────────────────────
    try:
        raw = str(value).strip()
    except Exception:
        return None

    if not raw:
        return None

    # ── Step 3: Remove currency symbols and whitespace ────────────────────────
    cleaned = _CURRENCY_PREFIX_RE.sub('', raw)
    cleaned = _WHITESPACE_RE.sub('', cleaned)
    cleaned = cleaned.strip()

    if not cleaned:
        return None

    # ── Step 4: Remove trailing/leading non-numeric fringe characters (e.g. "-") ─
    # Allow: digits, dot, comma, leading minus
    # Reject anything else
    if not re.match(r'^-?[\d.,]+$', cleaned):
        return None

    # ── Step 5: Apply Brazilian format conversion ─────────────────────────────
    has_comma = ',' in cleaned
    dot_count = cleaned.count('.')

    if has_comma:
        # Brazilian format: dots are thousands separators, comma is the decimal separator
        # "13.335,00" → remove dots → "13335,00" → replace comma → "13335.00"
        cleaned = cleaned.replace('.', '').replace(',', '.')
    elif dot_count > 1:
        # Multiple dots and no comma: all dots are thousands separators (no decimal part)
        # "13.335.000" → "13335000"
        cleaned = cleaned.replace('.', '')
    # else: single dot or no dot → already standard format ("13335.00" or "13335")

    # ── Step 6: Final validation ──────────────────────────────────────────────
    try:
        numeric = float(cleaned)
        if math.isnan(numeric) or math.isinf(numeric):
            return None
        # Reject negative numbers
        if numeric < 0:
            return None
        return cleaned
    except (ValueError, TypeError):
        return None
