"""
FlexFlow — Hardening Step 1 Validation Harness
================================================
Tests:
    H1-01  Backend reachable on port 8000
    H1-02  Path traversal blocked (400) — classic  ../../etc/passwd
    H1-03  Path traversal blocked (400) — Windows   C:\\Windows\\System32\\calc.exe
    H1-04  Path traversal blocked (400) — absolute  /etc/shadow
    H1-05  Valid tenant path accepted (not 400)
    H1-06  Invalid tenant_id format blocked (400)
    H1-07  AuditLog v1 hash is reproducible (backward compat)
    H1-08  AuditLog v2 hash includes tenant_id
    H1-09  AuditLog v2 hash differs from v1 for same inputs
    H1-10  verify_own_hash() returns True for a fresh v2 record
    H1-11  verify_own_hash() returns False if hash is tampered
    H1-12  calculate_hash_for_version raises ValueError for v2 without tenant_id
    H1-13  SECRET_KEY is loaded from env (not hardcoded fallback)

Run with:
    cd c:\\Documentos\\BotCase\\FlexFlow\\backend
    .\\venv\\Scripts\\Activate.ps1
    python -m pytest tests/test_hardening_s1.py -v
"""

import uuid
import hashlib
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

# ─── Path setup ────────────────────────────────────────────────────────────────
# Allow running from backend/ without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# ─── Constants ─────────────────────────────────────────────────────────────────
BACKEND_URL = "http://127.0.0.1:8000"
VALID_TENANT_ID = str(uuid.uuid4())       # Randomly generated for each run
VALID_ITEM_ID = uuid.uuid4()
VALID_USER_ID = uuid.uuid4()
VALID_TENANT_UUID = uuid.uuid4()
FIXED_TS = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)


# ==============================================================================
# H1-01 — Backend reachability
# ==============================================================================

class TestBackendReachability:
    """H1-01: Confirm the backend is reachable on port 8000."""

    def test_health_endpoint(self):
        """GET /health should return 200 with status=healthy."""
        try:
            import requests
        except ImportError:
            pytest.skip("requests library not installed")

        try:
            r = requests.get(f"{BACKEND_URL}/health", timeout=3)
        except Exception as e:
            pytest.skip(f"Backend not running on port 8000: {e}")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        body = r.json()
        assert body.get("status") == "healthy", f"Unexpected body: {body}"
        print(f"\n✅ H1-01 PASS — Backend healthy at {BACKEND_URL}/health")


# ==============================================================================
# H1-02 to H1-06 — Path traversal / FileService security
# ==============================================================================

class TestPathTraversalDefense:
    """H1-02 to H1-06: Verify _validate_safe_path blocks all traversal variants."""

    @pytest.fixture(autouse=True)
    def setup_file_service(self, tmp_path):
        """Create a FileService with a temp upload_dir for isolated testing."""
        # Import here to avoid side effects at collection time
        from backend.services.file_service import FileService
        from fastapi import HTTPException

        self.tmp_upload = tmp_path / "uploads"
        self.tmp_upload.mkdir()
        self.service = FileService(upload_dir=str(self.tmp_upload))
        self.HTTPException = HTTPException

        # Create tenant directory for valid path tests
        tenant_dir = self.tmp_upload / VALID_TENANT_ID
        tenant_dir.mkdir()
        # Create a real file inside the tenant dir for positive tests
        self.valid_file = tenant_dir / "document.pdf"
        self.valid_file.write_bytes(b"PDF content")

    def _assert_blocked(self, path_str: str, tenant_id: str):
        """Assert that _validate_safe_path raises HTTPException 400."""
        with pytest.raises(self.HTTPException) as exc_info:
            self.service._validate_safe_path(path_str, tenant_id)
        assert exc_info.value.status_code == 400, (
            f"Expected 400 for path='{path_str}', got {exc_info.value.status_code}"
        )

    def test_h1_02_classic_traversal(self):
        """H1-02: ../../etc/passwd must be blocked (400)."""
        self._assert_blocked("../../etc/passwd", VALID_TENANT_ID)
        print("\n✅ H1-02 PASS — Classic traversal blocked")

    def test_h1_03_windows_absolute_path(self):
        """H1-03: C:\\Windows\\System32\\calc.exe must be blocked (400)."""
        self._assert_blocked(r"C:\Windows\System32\calc.exe", VALID_TENANT_ID)
        print("\n✅ H1-03 PASS — Windows absolute path blocked")

    def test_h1_04_unix_absolute_path(self):
        """H1-04: /etc/shadow must be blocked (400)."""
        self._assert_blocked("/etc/shadow", VALID_TENANT_ID)
        print("\n✅ H1-04 PASS — Unix absolute path blocked")

    def test_h1_05_valid_tenant_path_accepted(self):
        """H1-05: A well-formed path inside the tenant directory is NOT blocked."""
        valid_path = str(self.tmp_upload / VALID_TENANT_ID / "document.pdf")
        # Should NOT raise
        result = self.service._validate_safe_path(valid_path, VALID_TENANT_ID)
        assert result is not None
        print(f"\n✅ H1-05 PASS — Valid path accepted: {result}")

    def test_h1_06_invalid_tenant_id_blocked(self):
        """H1-06: A non-UUID tenant_id is rejected before path operations."""
        bad_tenant_ids = [
            "../../../admin",
            "'; DROP TABLE tenants; --",
            "",
            "not-a-uuid",
            "/etc",
        ]
        for bad_id in bad_tenant_ids:
            self._assert_blocked("uploads/any/file.pdf", bad_id)
        print("\n✅ H1-06 PASS — All invalid tenant_id formats blocked")

    def test_h1_cross_tenant_path_blocked(self):
        """Bonus: Accessing another tenant's file using own tenant_id is blocked."""
        other_tenant = str(uuid.uuid4())
        other_dir = self.tmp_upload / other_tenant
        other_dir.mkdir()
        other_file = other_dir / "secret.pdf"
        other_file.write_bytes(b"secret")

        # Attacker uses their own valid tenant_id but tries to reach other tenant's file
        self._assert_blocked(str(other_file), VALID_TENANT_ID)
        print("\n✅ BONUS PASS — Cross-tenant file access blocked")


# ==============================================================================
# H1-07 to H1-13 — AuditLog hash versioning
# ==============================================================================

class TestAuditLogHashVersioning:
    """H1-07 to H1-13: Verify hash v1/v2 logic in AuditLog model."""

    @pytest.fixture(autouse=True)
    def import_audit_log(self):
        from backend.models import AuditLog
        self.AuditLog = AuditLog

    def _v1_hash(self, item_id=None, from_s=None, to_s="APPROVED",
                 ts=FIXED_TS, prev=None, user=None):
        return self.AuditLog.calculate_hash(
            item_id=item_id or VALID_ITEM_ID,
            from_status=from_s,
            to_status=to_s,
            timestamp=ts,
            previous_hash=prev,
            changed_by=user
        )

    def _v2_hash(self, tenant_id=None, item_id=None, from_s=None, to_s="APPROVED",
                 ts=FIXED_TS, prev=None, user=None):
        return self.AuditLog.calculate_hash_v2(
            tenant_id=tenant_id or VALID_TENANT_UUID,
            item_id=item_id or VALID_ITEM_ID,
            from_status=from_s,
            to_status=to_s,
            timestamp=ts,
            previous_hash=prev,
            changed_by=user
        )

    def test_h1_07_v1_hash_reproducible(self):
        """H1-07: V1 hash is deterministic — same inputs → same hash."""
        h1 = self._v1_hash()
        h2 = self._v1_hash()
        assert h1 == h2, "V1 hash is not deterministic"
        assert len(h1) == 64, f"SHA-256 hash should be 64 chars, got {len(h1)}"
        print(f"\n✅ H1-07 PASS — V1 hash reproducible: {h1[:16]}...")

    def test_h1_08_v2_hash_includes_tenant_id(self):
        """H1-08: V2 hash for tenant_A ≠ V2 hash for tenant_B (same item)."""
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        h_a = self._v2_hash(tenant_id=tenant_a)
        h_b = self._v2_hash(tenant_id=tenant_b)
        assert h_a != h_b, (
            "V2 hashes for different tenants are identical — tenant_id not included!"
        )
        print(f"\n✅ H1-08 PASS — V2 hash is tenant-scoped")

    def test_h1_09_v2_differs_from_v1(self):
        """H1-09: V2 hash ≠ V1 hash for same inputs (tenant_id changes the digest)."""
        h_v1 = self._v1_hash()
        h_v2 = self._v2_hash()
        assert h_v1 != h_v2, (
            "V1 and V2 hashes are identical — tenant_id is not affecting the digest!"
        )
        print(f"\n✅ H1-09 PASS — V2 ≠ V1 for same inputs")

    def test_h1_10_verify_own_hash_valid(self):
        """H1-10: verify_own_hash() returns True for a correctly constructed v2 record."""
        AuditLog = self.AuditLog
        tenant_id = uuid.uuid4()
        item_id = uuid.uuid4()
        ts = FIXED_TS
        computed_hash = AuditLog.calculate_hash_v2(
            tenant_id=tenant_id,
            item_id=item_id,
            from_status="PENDING",
            to_status="APPROVED",
            timestamp=ts,
            previous_hash=None,
            changed_by=None
        )

        # Use SimpleNamespace as a plain-Python mock — avoids SQLAlchemy ORM instrumentation
        # verify_own_hash() only reads attributes; it doesn’t need ORM internals.
        log = types.SimpleNamespace(
            hash_version=AuditLog.HASH_VERSION_CURRENT,
            item_id=item_id,
            from_status="PENDING",
            to_status="APPROVED",
            created_at=ts,
            previous_hash=None,
            changed_by=None,
            hash=computed_hash
        )
        # Bind the method to our SimpleNamespace object
        result = AuditLog.verify_own_hash(log, tenant_id=tenant_id)

        assert result is True
        print(f"\n✅ H1-10 PASS — verify_own_hash() True for valid v2 record")

    def test_h1_11_verify_own_hash_detects_tampering(self):
        """H1-11: verify_own_hash() returns False if the stored hash is tampered."""
        AuditLog = self.AuditLog

        # Same SimpleNamespace approach — deliberately wrong hash value
        log = types.SimpleNamespace(
            hash_version=AuditLog.HASH_VERSION_CURRENT,
            item_id=VALID_ITEM_ID,
            from_status="PENDING",
            to_status="APPROVED",
            created_at=FIXED_TS,
            previous_hash=None,
            changed_by=None,
            hash="a" * 64  # deliberately wrong
        )
        result = AuditLog.verify_own_hash(log, tenant_id=VALID_TENANT_UUID)

        assert result is False
        print(f"\n✅ H1-11 PASS — verify_own_hash() False for tampered record")

    def test_h1_12_v2_without_tenant_raises(self):
        """H1-12: calculate_hash_for_version(v=2, tenant_id=None) raises ValueError."""
        with pytest.raises(ValueError, match="tenant_id is required"):
            self.AuditLog.calculate_hash_for_version(
                version=self.AuditLog.HASH_VERSION_CURRENT,
                item_id=VALID_ITEM_ID,
                from_status=None,
                to_status="APPROVED",
                timestamp=FIXED_TS,
                previous_hash=None,
                changed_by=None,
                tenant_id=None  # ← This should raise
            )
        print(f"\n✅ H1-12 PASS — ValueError raised when tenant_id missing for v2")

    def test_h1_13_secret_key_loaded_from_env(self):
        """H1-13: auth.py and middleware.py must load SECRET_KEY from .env, not hardcode it."""
        env_path = Path(__file__).resolve().parent.parent / ".env"
        assert env_path.exists(), f".env not found at {env_path}"

        # Check that .env contains SECRET_KEY key
        env_content = env_path.read_text(encoding="utf-8")
        assert "SECRET_KEY=" in env_content, (
            "SECRET_KEY is not present in .env — add it before production deployment"
        )

        # Check that neither source file contains the old hardcoded string as an assignment
        auth_path = Path(__file__).resolve().parent.parent / "routers" / "auth.py"
        middleware_path = Path(__file__).resolve().parent.parent / "middleware.py"

        for fp in [auth_path, middleware_path]:
            content = fp.read_text(encoding="utf-8")
            # The old pattern was: SECRET_KEY = "your-secret-key-here..."
            # New pattern should use os.getenv — check no raw assignment remains
            assert 'SECRET_KEY = "your-secret-key' not in content, (
                f"Hardcoded SECRET_KEY assignment still present in {fp.name}! "
                "Replace with os.getenv('SECRET_KEY')."
            )

        print(f"\n✅ H1-13 PASS — SECRET_KEY sourced from .env in both auth.py and middleware.py")


# ==============================================================================
# Summary
# ==============================================================================

if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(Path(__file__).resolve().parent.parent)
    )
    sys.exit(result.returncode)
