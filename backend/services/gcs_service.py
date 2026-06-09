"""
FlexFlow GCS Service
Handles file uploads to Google Cloud Storage with validation, unique naming, and content-type headers.
"""

import os
import io
import time
import logging
from pathlib import Path
from typing import Tuple, Optional
from fastapi import UploadFile, HTTPException, status
from google.cloud import storage

logger = logging.getLogger(__name__)


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
        
        # Local development credentials detection
        local_key_path = "backend/gcp-key.json"
        if os.path.exists(local_key_path) and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(local_key_path)
            logger.info(f"Loaded local GCP credentials from {local_key_path}")
            
        try:
            self.client = storage.Client()
            self.bucket = self.client.bucket(self.bucket_name)
        except Exception as e:
            logger.error(f"Failed to initialize GCS Client: {e}")
            self.client = None
            self.bucket = None

    def validate_file(self, file: UploadFile) -> Tuple[bool, Optional[str]]:
        """
        Validate file extension and size
        """
        if not file.filename:
            return False, "No filename provided"
            
        safe_filename = os.path.basename(file.filename)
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
            
        # Unique Naming Strategy
        safe_filename = os.path.basename(file.filename) if file.filename else "unknown"
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
