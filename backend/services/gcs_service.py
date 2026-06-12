"""
FlexFlow GCS Service — with Local Filesystem Fallback
Handles file uploads to Google Cloud Storage with validation, unique naming,
and content-type headers.

Fallback Strategy (FF-HARDENING-008):
  If GCS write returns 403 (missing storage.objects.create IAM permission) or
  any other storage error, the service saves the file to backend/uploads/ and
  returns a local /api/uploads/download?path=... URL instead.  This ensures
  uploads work immediately in the local-dev / broken-IAM scenario without any
  code change on the caller side — the caller receives the same (url, filename)
  tuple regardless of which storage backend was used.

Async-safety fix (FF-HARDENING-008):
  blob.upload_from_file() is a blocking synchronous GCS call.  Running it
  directly inside an `async def` FastAPI handler blocks the uvicorn event loop.
  We now use asyncio.get_event_loop().run_in_executor(None, ...) to offload
  the blocking I/O to the default thread-pool, keeping the event loop free.
"""

import os
import io
import time
import asyncio
import logging
from pathlib import Path, PureWindowsPath
from typing import Tuple, Optional
from fastapi import UploadFile, HTTPException, status

logger = logging.getLogger(__name__)

try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except Exception as e:
    logger.error(f"Failed to import google-cloud-storage: {e}")
    GCS_AVAILABLE = False


def get_safe_filename(filename: str) -> str:
    """
    Safely extracts the file base name, handling both POSIX and Windows paths correctly.

    On Linux, os.path.basename does NOT split backslashes, so a Windows path like
    'C:\\Users\\John\\file.jpg' would be returned verbatim. PureWindowsPath correctly
    extracts the last path component on any operating system.

    Args:
        filename: Raw filename string from the UploadFile (may contain Windows full path).

    Returns:
        The sanitized base filename only (e.g. 'file.jpg').
    """
    return PureWindowsPath(filename).name


# ── Local uploads directory (fallback when GCS write is unavailable) ──────────
# Resolved relative to this file's location: backend/services/ → backend/uploads/
_LOCAL_UPLOADS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "uploads")
)


def _save_locally(content: bytes, blob_name: str) -> str:
    """
    Save *content* to the local uploads directory, mirroring the GCS blob path.
    Returns the local filesystem path (not a URL; the caller constructs the URL).
    """
    local_path = os.path.join(_LOCAL_UPLOADS_DIR, blob_name.replace("/", os.sep))
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "wb") as fh:
        fh.write(content)
    return local_path


class GCSService:
    """Service for handling file uploads — GCS primary, local filesystem fallback."""

    ALLOWED_EXTENSIONS = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png'
    }

    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

    def __init__(self):
        """Initialize Google Cloud Storage Client."""
        self.bucket_name = os.getenv("GCP_BUCKET_NAME", "flexflow-attachments-224292950652")
        self.client = None
        self.bucket = None

        if not GCS_AVAILABLE:
            logger.warning("google-cloud-storage not importable — uploads will use local fallback.")
            return

        # Local development credentials detection
        local_key_path = "backend/gcp-key.json"
        if os.path.exists(local_key_path) and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(local_key_path)
            logger.info(f"Loaded local GCP credentials from {local_key_path}")

        try:
            print(f"DEBUG GCS: Attempting to access bucket {self.bucket_name}", flush=True)
            storage_client = storage.Client()
            self.client = storage_client
            print(f"DEBUG GCS: Client initialized with project {storage_client.project}", flush=True)
            self.bucket = storage_client.bucket(self.bucket_name)
        except Exception as e:
            print(f"DEBUG GCS ERROR: Failed to initialize/access bucket: {e}", flush=True)
            logger.error(f"Failed to initialize GCS Client: {e}")
            self.client = None
            self.bucket = None

    def validate_file(self, file: UploadFile) -> Tuple[bool, Optional[str]]:
        """
        Validate file extension and size.
        Uses get_safe_filename() (PureWindowsPath) to correctly handle Windows paths
        sent from Windows browsers, where os.path.basename would fail on Linux.
        """
        if not file.filename:
            return False, "No filename provided"

        safe_filename = get_safe_filename(file.filename)
        file_ext = Path(safe_filename).suffix.lower()

        if file_ext not in self.ALLOWED_EXTENSIONS:
            allowed = ', '.join(self.ALLOWED_EXTENSIONS.keys())
            return False, f"Invalid file type. Allowed types: {allowed}"

        return True, None

    async def upload_file(self, file: UploadFile, identifier: str) -> Tuple[str, str]:
        """
        Upload file to GCS (primary) or local filesystem (fallback).

        Returns a tuple (public_url, safe_filename) regardless of which backend
        was used, so all callers remain identical.

        Async-safety: the blocking GCS I/O is offloaded to a thread-pool executor
        so the uvicorn event loop is never blocked.
        """
        is_valid, error_msg = self.validate_file(file)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

        content = await file.read()
        if len(content) > self.MAX_FILE_SIZE:
            size_mb = self.MAX_FILE_SIZE / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds {size_mb:.0f}MB limit"
            )

        # ── Build canonical blob name ─────────────────────────────────────────
        safe_filename = get_safe_filename(file.filename) if file.filename else "unknown"
        timestamp     = int(time.time())
        blob_name     = f"attachments/{identifier}/{timestamp}_{safe_filename}"

        # ── Determine content type ────────────────────────────────────────────
        file_ext     = Path(safe_filename).suffix.lower()
        content_type = self.ALLOWED_EXTENSIONS.get(file_ext, file.content_type or "application/octet-stream")

        # ── Attempt GCS upload ────────────────────────────────────────────────
        if self.bucket is not None:
            try:
                blob      = self.bucket.blob(blob_name)
                file_like = io.BytesIO(content)

                # FF-HARDENING-008: run blocking GCS I/O in a thread-pool so the
                # asyncio event loop is never blocked by synchronous network I/O.
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: blob.upload_from_file(file_like, content_type=content_type)
                )

                public_url = f"https://storage.googleapis.com/{self.bucket_name}/{blob_name}"
                print(f"[GCS] Uploaded to: {public_url}", flush=True)
                return public_url, safe_filename

            except Exception as e:
                # 403 = missing storage.objects.create — fall through to local backup
                err_str = str(e)
                print(f"[GCS] Upload failed ({type(e).__name__}): {err_str[:200]}", flush=True)
                logger.warning(
                    f"GCS upload failed for {blob_name}: {e}. "
                    "Falling back to local filesystem storage."
                )
                # Fall through to local fallback below
        else:
            print("[GCS] Bucket not initialized — using local filesystem fallback.", flush=True)

        # ── Local filesystem fallback ─────────────────────────────────────────
        try:
            local_path = _save_locally(content, blob_name)
            # Construct a URL the backend's /api/uploads/download endpoint can serve
            local_url  = f"/api/uploads/download?path={blob_name.replace(os.sep, '/')}"
            print(f"[LOCAL] Saved to: {local_path}", flush=True)
            print(f"[LOCAL] Serving via: {local_url}", flush=True)
            return local_url, safe_filename
        except Exception as local_err:
            logger.error(f"Local fallback also failed for {blob_name}: {local_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store file (GCS and local fallback both failed): {local_err}"
            )
