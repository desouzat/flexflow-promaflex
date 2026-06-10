"""
FlexFlow — FF-HARDENING-001: Attachment Persistence & Path Sanitization Tests
==============================================================================

Tests:
    AP-01  get_safe_filename returns only the basename for a simple filename
    AP-02  get_safe_filename strips Windows absolute path (C:\\Users\\John\\file.jpg)
    AP-03  get_safe_filename strips Windows path with drive letter only
    AP-04  get_safe_filename strips mixed-slash Windows path
    AP-05  get_safe_filename handles POSIX path correctly (returns basename)
    AP-06  get_safe_filename handles filename with no directory component
    AP-07  flag_modified is importable from sqlalchemy.orm.attributes
    AP-08  extra_metadata attachments list initializes from None to []
    AP-09  Appending to extra_metadata["attachments"] accumulates entries
    AP-10  Each attachment dict contains required keys: filename, url, timestamp

Run with:
    cd C:\\Documentos\\BotCase\\FlexFlow\\backend
    .\\venv\\Scripts\\Activate.ps1
    python -m pytest tests/test_attachment_persistence.py -v
"""

import sys
from pathlib import Path
from datetime import datetime

import pytest

# ─── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


# ==============================================================================
# AP-01 to AP-06 — Windows Path Sanitization via PureWindowsPath
# ==============================================================================

class TestGetSafeFilename:
    """
    AP-01 to AP-06: Verifies that get_safe_filename() from gcs_service correctly
    extracts the bare filename from both POSIX and Windows paths using PureWindowsPath.
    """

    @pytest.fixture(autouse=True)
    def import_helper(self):
        from backend.services.gcs_service import get_safe_filename
        self.get_safe_filename = get_safe_filename

    def test_ap01_simple_filename(self):
        """AP-01: A simple filename (no directory) is returned unchanged."""
        result = self.get_safe_filename("document.pdf")
        assert result == "document.pdf", f"Expected 'document.pdf', got '{result}'"
        print("\n✅ AP-01 PASS — Simple filename returned correctly")

    def test_ap02_windows_absolute_path(self):
        """AP-02: Full Windows path 'C:\\Users\\John\\file.jpg' → 'file.jpg'."""
        result = self.get_safe_filename(r"C:\Users\JohnDoc\file.jpg")
        assert result == "file.jpg", (
            f"Expected 'file.jpg' from Windows absolute path, got '{result}'. "
            "os.path.basename() fails on Linux for backslash paths; use PureWindowsPath."
        )
        print("\n✅ AP-02 PASS — Windows absolute path sanitized correctly")

    def test_ap03_windows_path_drive_and_nested(self):
        """AP-03: Deeply nested Windows path → last component only."""
        result = self.get_safe_filename(r"C:\Users\Thiago\Documents\Promaflex\NF_emitida.pdf")
        assert result == "NF_emitida.pdf", f"Expected 'NF_emitida.pdf', got '{result}'"
        print("\n✅ AP-03 PASS — Deeply nested Windows path sanitized correctly")

    def test_ap04_windows_mixed_slashes(self):
        """AP-04: Windows path with mixed slashes → last component only."""
        result = self.get_safe_filename(r"C:\My Files/uploads\test_image.png")
        assert result == "test_image.png", f"Expected 'test_image.png', got '{result}'"
        print("\n✅ AP-04 PASS — Mixed-slash Windows path sanitized correctly")

    def test_ap05_posix_path(self):
        """AP-05: POSIX absolute path '/home/user/uploads/doc.pdf' → 'doc.pdf'."""
        result = self.get_safe_filename("/home/user/uploads/doc.pdf")
        assert result == "doc.pdf", f"Expected 'doc.pdf', got '{result}'"
        print("\n✅ AP-05 PASS — POSIX absolute path sanitized correctly")

    def test_ap06_no_directory_component(self):
        """AP-06: Filename without any path separator is returned as-is."""
        result = self.get_safe_filename("canhoto_fake.jpg")
        assert result == "canhoto_fake.jpg", f"Expected 'canhoto_fake.jpg', got '{result}'"
        print("\n✅ AP-06 PASS — Filename with no directory component returned as-is")


# ==============================================================================
# AP-07 — SQLAlchemy flag_modified import check
# ==============================================================================

class TestFlagModifiedImport:
    """AP-07: Verify that flag_modified can be imported from sqlalchemy.orm.attributes."""

    def test_ap07_flag_modified_importable(self):
        """AP-07: flag_modified must be importable without error."""
        from sqlalchemy.orm.attributes import flag_modified
        assert callable(flag_modified), "flag_modified must be a callable function"
        print("\n✅ AP-07 PASS — flag_modified importable from sqlalchemy.orm.attributes")


# ==============================================================================
# AP-08 to AP-10 — extra_metadata["attachments"] JSONB mutation logic
# ==============================================================================

class TestAttachmentMetadataPersistence:
    """
    AP-08 to AP-10: Validates the in-memory JSONB mutation pattern that must be used
    before calling flag_modified() and db.commit(). These tests verify the logic
    without requiring a live database connection.
    """

    def _apply_attachment(
        self,
        extra_metadata: dict | None,
        filename: str,
        url: str,
        attachment_type: str = "cargo_photo"
    ) -> dict:
        """
        Simulate the persistence pattern from the upload endpoints.
        Mirrors the exact code block added to upload_cargo_photo / upload_receipt_photo.
        """
        from backend.services.gcs_service import get_safe_filename

        # 1. Sanitize filename
        safe_filename = get_safe_filename(filename)

        # 2. Initialize metadata if empty (mirrors the endpoint logic)
        if not extra_metadata:
            extra_metadata = {}

        if "attachments" not in extra_metadata:
            extra_metadata["attachments"] = []

        # 3. Append new attachment entry
        extra_metadata["attachments"].append({
            "filename": safe_filename,
            "url": url,
            "type": attachment_type,
            "timestamp": datetime.utcnow().isoformat()
        })

        return extra_metadata

    def test_ap08_initializes_from_none(self):
        """AP-08: extra_metadata=None must be initialized to {} before appending."""
        result = self._apply_attachment(
            extra_metadata=None,
            filename="foto_carga.jpg",
            url="https://storage.googleapis.com/flexflow-attachments-224292950652/attachments/po-123/1234567890_foto_carga.jpg"
        )
        assert isinstance(result, dict), "Result must be a dict"
        assert "attachments" in result, "'attachments' key must be created"
        assert isinstance(result["attachments"], list), "'attachments' value must be a list"
        assert len(result["attachments"]) == 1, "One attachment must be appended"
        print("\n✅ AP-08 PASS — extra_metadata initialized from None correctly")

    def test_ap09_accumulates_multiple_attachments(self):
        """AP-09: Subsequent uploads append to (not overwrite) the attachments list."""
        meta = {}
        meta = self._apply_attachment(meta, r"C:\Photos\cargo1.jpg", "https://gcs.example.com/cargo1.jpg", "cargo_photo")
        meta = self._apply_attachment(meta, r"C:\Photos\receipt1.jpg", "https://gcs.example.com/receipt1.jpg", "receipt_photo")

        assert len(meta["attachments"]) == 2, (
            f"Expected 2 attachments after 2 uploads, got {len(meta['attachments'])}"
        )
        assert meta["attachments"][0]["type"] == "cargo_photo"
        assert meta["attachments"][1]["type"] == "receipt_photo"
        print("\n✅ AP-09 PASS — Multiple attachments accumulate correctly in list")

    def test_ap10_attachment_has_required_keys(self):
        """AP-10: Each attachment dict must contain 'filename', 'url', 'timestamp'."""
        meta = self._apply_attachment(
            extra_metadata=None,
            filename=r"C:\MyFiles\test_image.png",
            url="https://storage.googleapis.com/bucket/test_image.png"
        )
        entry = meta["attachments"][0]

        required_keys = {"filename", "url", "timestamp"}
        missing = required_keys - set(entry.keys())
        assert not missing, f"Attachment entry is missing required keys: {missing}"

        # AP-10a: Filename must be sanitized (only basename, no path)
        assert entry["filename"] == "test_image.png", (
            f"Expected sanitized filename 'test_image.png', got '{entry['filename']}'. "
            "Windows path sanitization via PureWindowsPath is not working."
        )

        # AP-10b: URL must be preserved exactly
        assert entry["url"] == "https://storage.googleapis.com/bucket/test_image.png"

        # AP-10c: Timestamp must be a valid ISO 8601 string
        assert isinstance(entry["timestamp"], str), "timestamp must be a string"
        datetime.fromisoformat(entry["timestamp"])  # raises if invalid

        print(f"\n✅ AP-10 PASS — Attachment dict contains all required keys with correct values")
        print(f"   → filename : {entry['filename']!r}")
        print(f"   → url      : {entry['url']!r}")
        print(f"   → timestamp: {entry['timestamp']!r}")


# ==============================================================================
# Summary runner
# ==============================================================================

if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(Path(__file__).resolve().parent.parent)
    )
    sys.exit(result.returncode)
