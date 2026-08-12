import pytest
from datetime import datetime
from backend.routers.reports import safe_format_date, safe_get_field

def test_safe_format_date():
    assert safe_format_date(None) == ""
    assert safe_format_date("") == ""
    assert safe_format_date(datetime(2026, 8, 19)) == "19/08/2026"
    assert safe_format_date("2026-08-21") == "21/08/2026"
    assert safe_format_date("19/08/2026") == "19/08/2026"

def test_safe_get_field():
    assert safe_get_field(None, "key") == ""
    assert safe_get_field(None, "key", None) is None
    assert safe_get_field({}, "key", "default") == "default"
    assert safe_get_field({"a": 1}, "a") == 1
    assert safe_get_field('{"a": 2}', "a") == 2
    assert safe_get_field("invalid json", "a", "fallback") == "fallback"
    assert safe_get_field(12345, "a", "fallback") == "fallback"
