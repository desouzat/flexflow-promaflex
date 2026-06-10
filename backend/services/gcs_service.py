"""
FlexFlow GCS Service
Handles file uploads to Google Cloud Storage with validation, unique naming, and content-type headers.
"""

import os
import io
import time
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


class GCSService:
    """Service for handling file uploads directly to Google Cloud Storage"""
    
    ALLOWED_EXTENSIONS = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png'
    }
    
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes
    
    def __init__(self):
        """Initialize Google Cloud Storage Client"""
        self.bucket_name = os.getenv("GCP_BUCKET_NAME", "flexflow-attachments-224292950652")
        self.client = None
        self.bucket = None
        
        if not GCS_AVAILABLE:
            logger.error("GCS_AVAILABLE is False. Google Cloud Storage will not be functional.")
            return
        
        # Local development credentials detection
        local_key_path = "backend/gcp-key.json"
        if os.path.exists(local_key_path) and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(local_key_path)
            logger.info(f"Loaded local GCP credentials from {local_key_path}")
            
        try:
            bucket_name = self.bucket_name
            print(f"DEBUG GCS: Attempting to access bucket {bucket_name}", flush=True)
            storage_client = storage.Client()
            self.client = storage_client
            print(f"DEBUG GCS: Client initialized with project {storage_client.project}", flush=True)
            self.bucket = storage_client.bucket(bucket_name)
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
        Upload file to GCS with unique naming:
        attachments/{identifier}/{timestamp}_{original_filename}
        
        Sets proper Content-Type metadata during upload using upload_from_file.
        """
        is_valid, error_msg = self.validate_file(file)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
            
        content = await file.read()
        if len(content) > self.MAX_FILE_SIZE:
            size_mb = self.MAX_FILE_SIZE / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds {size_mb}MB limit"
            )
            
        if not self.bucket:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GCS storage service is not initialized"
            )
            
        # Unique Naming Strategy — use PureWindowsPath to handle Windows-browser uploads
        # where the filename may contain full Windows paths (e.g. C:\Users\John\file.jpg).
        safe_filename = get_safe_filename(file.filename) if file.filename else "unknown"
        timestamp = int(time.time())
        blob_name = f"attachments/{identifier}/{timestamp}_{safe_filename}"
        
        # Determine content type
        file_ext = Path(safe_filename).suffix.lower()
        content_type = self.ALLOWED_EXTENSIONS.get(file_ext, file.content_type or "application/octet-stream")
        
        try:
            blob = self.bucket.blob(blob_name)
            
            # Wrap content in a file-like object to call upload_from_file for Harness H-20
            file_like = io.BytesIO(content)
            blob.upload_from_file(file_like, content_type=content_type)
            
            # Return the GCS Public URL and original filename
            public_url = f"https://storage.googleapis.com/{self.bucket_name}/{blob_name}"
            return public_url, safe_filename
        except Exception as e:
            logger.error(f"GCS upload failed for {blob_name}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file to storage: {str(e)}"
            )
