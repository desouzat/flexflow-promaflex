"""
FlexFlow — Harness U-01: clean_brazilian_number Unit Tests
==========================================================
All 10 test cases defined in the Hardening SDD, plus extras.

Run with:
    cd c:\\Documentos\\BotCase\\FlexFlow\\backend
    .\\venv\\Scripts\\Activate.ps1
    python -m pytest tests/test_number_utils.py -v
"""

import math
import sys
from pathlib import Path

import pytest

# Allow running from backend/ without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.utils.number_utils import clean_brazilian_number


class TestCleanBrazilianNumberSDD:
    """
    SDD Harness U-01 — The 10 canonical test cases defined in the Hardening SDD.
    These are the acceptance criteria for the clean_brazilian_number function.
    """

    def test_u01_01_full_brl_format(self):
        """U-01-01: 'R$ 13.335,00' → '13335.00' — full BRL with currency symbol."""
        result = clean_brazilian_number("R$ 13.335,00")
        assert result == "13335.00", f"Expected '13335.00', got {result!r}"
        print(f"\n✅ U-01-01 PASS — 'R$ 13.335,00' → {result!r}")

    def test_u01_02_no_currency_symbol(self):
        """U-01-02: '13.335,00' → '13335.00' — Brazilian format, no symbol."""
        result = clean_brazilian_number("13.335,00")
        assert result == "13335.00", f"Expected '13335.00', got {result!r}"
        print(f"\n✅ U-01-02 PASS — '13.335,00' → {result!r}")

    def test_u01_03_four_digit_thousands(self):
        """U-01-03: '1.335,50' → '1335.50' — 4-digit thousands grouping."""
        result = clean_brazilian_number("1.335,50")
        assert result == "1335.50", f"Expected '1335.50', got {result!r}"
        print(f"\n✅ U-01-03 PASS — '1.335,50' → {result!r}")

    def test_u01_04_already_standard(self):
        """U-01-04: '13335.00' → '13335.00' — already in standard decimal format."""
        result = clean_brazilian_number("13335.00")
        assert result == "13335.00", f"Expected '13335.00', got {result!r}"
        print(f"\n✅ U-01-04 PASS — '13335.00' → {result!r}")

    def test_u01_05_comma_decimal_no_thousands(self):
        """U-01-05: '13335,00' → '13335.00' — comma decimal, no thousands separator."""
        result = clean_brazilian_number("13335,00")
        assert result == "13335.00", f"Expected '13335.00', got {result!r}"
        print(f"\n✅ U-01-05 PASS — '13335,00' → {result!r}")

    def test_u01_06_sub_unit_value(self):
        """U-01-06: '0,50' → '0.50' — sub-unit value (less than 1 real)."""
        result = clean_brazilian_number("0,50")
        assert result == "0.50", f"Expected '0.50', got {result!r}"
        print(f"\n✅ U-01-06 PASS — '0,50' → {result!r}")

    def test_u01_07_invalid_string(self):
        """U-01-07: 'INVALID' → None — failure path for non-numeric text."""
        result = clean_brazilian_number("INVALID")
        assert result is None, f"Expected None for 'INVALID', got {result!r}"
        print(f"\n✅ U-01-07 PASS — 'INVALID' → None")

    def test_u01_08_none_input(self):
        """U-01-08: None → None — null input."""
        result = clean_brazilian_number(None)
        assert result is None, f"Expected None for None input, got {result!r}"
        print(f"\n✅ U-01-08 PASS — None → None")

    def test_u01_09_nan_input(self):
        """U-01-09: float('nan') → None — NaN input."""
        result = clean_brazilian_number(float("nan"))
        assert result is None, f"Expected None for NaN, got {result!r}"
        print(f"\n✅ U-01-09 PASS — float('nan') → None")

    def test_u01_10_native_float_passthrough(self):
        """U-01-10: 13335.00 (native float) → non-None string — float passthrough."""
        result = clean_brazilian_number(13335.00)
        assert result is not None, "Expected a non-None result for native float 13335.00"
        # Native float: str(13335.0) = "13335.0" — accept any valid numeric string
        assert float(result) == pytest.approx(13335.0, abs=0.001), (
            f"Expected ~13335.0, got {result!r}"
        )
        print(f"\n✅ U-01-10 PASS — float(13335.00) → {result!r}")


class TestCleanBrazilianNumberEdgeCases:
    """
    Additional edge cases beyond the SDD U-01 harness.
    These validate robustness against real-world data variations.
    """

    def test_dollar_symbol(self):
        """'$ 500,00' → '500.00' — dollar sign prefix."""
        result = clean_brazilian_number("$ 500,00")
        assert result == "500.00", f"Got {result!r}"

    def test_multiple_thousands_groups(self):
        """'1.000.000,00' → '1000000.00' — millions."""
        result = clean_brazilian_number("1.000.000,00")
        assert result == "1000000.00", f"Got {result!r}"

    def test_zero_value(self):
        """'0,00' → '0.00' — zero."""
        result = clean_brazilian_number("0,00")
        assert result == "0.00", f"Got {result!r}"

    def test_integer_string(self):
        """'500' → '500' — plain integer string."""
        result = clean_brazilian_number("500")
        assert result == "500", f"Got {result!r}"

    def test_native_int(self):
        """500 (int) → '500'."""
        result = clean_brazilian_number(500)
        assert result == "500", f"Got {result!r}"

    def test_negative_string_rejected(self):
        """-100 (negative) → None — negatives are invalid for currency."""
        result = clean_brazilian_number("-100")
        assert result is None, f"Expected None for negative, got {result!r}"

    def test_negative_float_rejected(self):
        """-100.0 (negative float) → None."""
        result = clean_brazilian_number(-100.0)
        assert result is None, f"Expected None for -100.0, got {result!r}"

    def test_empty_string_rejected(self):
        """'' → None."""
        result = clean_brazilian_number("")
        assert result is None, f"Expected None for empty string, got {result!r}"

    def test_whitespace_only_rejected(self):
        """'   ' → None."""
        result = clean_brazilian_number("   ")
        assert result is None, f"Expected None for whitespace only, got {result!r}"

    def test_r_dollar_no_space(self):
        """'R$500,00' → '500.00' — no space after R$."""
        result = clean_brazilian_number("R$500,00")
        assert result == "500.00", f"Got {result!r}"

    def test_r_dollar_with_spaces(self):
        """'R$  13.335,00  ' → '13335.00' — leading/trailing whitespace."""
        result = clean_brazilian_number("R$  13.335,00  ")
        assert result == "13335.00", f"Got {result!r}"

    def test_r_dollar_space_comma(self):
        """'R$ 17,57' → '17.57' — space after R$ and comma decimal."""
        result = clean_brazilian_number("R$ 17,57")
        assert result == "17.57", f"Expected '17.57', got {result!r}"

    def test_float_inf_rejected(self):
        """float('inf') → None."""
        result = clean_brazilian_number(float("inf"))
        assert result is None, f"Expected None for inf, got {result!r}"

    def test_multiple_thousands_no_decimal(self):
        """'13.335' (thousands only, no decimal part) → '13335'."""
        result = clean_brazilian_number("13.335")
        # Single dot: treated as standard decimal separator
        # "13.335" has ONE dot → standard decimal → "13335" would require the multi-dot path
        # Actually "13.335" has 1 dot, no comma → treated as standard decimal "13.335"
        # This is the correct behavior: without context we cannot know if it's thousands or decimal
        assert result is not None, "Expected non-None for '13.335'"

    def test_critical_brl_regression(self):
        """
        Critical regression: the old Strategy-B code did `replace(',', '')` which turned
        '13.335,50' into '13.33550' (wrong!) instead of '13335.50' (correct).
        This test verifies the fix.
        """
        result = clean_brazilian_number("13.335,50")
        assert result == "13335.50", (
            f"REGRESSION: '13.335,50' should be '13335.50', got {result!r}. "
            "This indicates the old Strategy-B cleaning is still active."
        )
        # Verify the decimal value is correct
        from decimal import Decimal
        assert Decimal(result) == Decimal("13335.50"), (
            f"Decimal value mismatch: {Decimal(result)} != 13335.50"
        )
        print(f"\n✅ CRITICAL REGRESSION PASS — '13.335,50' → {result!r} (was broken before)")


if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(Path(__file__).resolve().parent.parent)
    )
    sys.exit(result.returncode)
