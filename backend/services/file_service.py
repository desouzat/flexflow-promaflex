"""
FlexFlow File Service
Handles file uploads with UUID renaming and validation
"""

import os
import uuid
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException, status


class FileService:
    """Service for handling file uploads with validation and UUID renaming"""
    
    # Allowed file extensions and their MIME types
    ALLOWED_EXTENSIONS = {
        '.pdf': ['application/pdf'],
        '.jpg': ['image/jpeg'],
        '.jpeg': ['image/jpeg'],
        '.png': ['image/png']
    }
    
    # Maximum file size (5MB)
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes
    
    def __init__(self, upload_dir: str = "backend/uploads"):
        """
        Initialize FileService
        
        Args:
            upload_dir: Directory where files will be stored
        """
        self.upload_dir = Path(upload_dir)
        self._ensure_upload_dir_exists()
    
    def _ensure_upload_dir_exists(self):
        """Create upload directory if it doesn't exist"""
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Create .gitkeep if it doesn't exist
        gitkeep_path = self.upload_dir / ".gitkeep"
        if not gitkeep_path.exists():
            gitkeep_path.touch()
    
    def validate_file(self, file: UploadFile) -> Tuple[bool, Optional[str]]:
        """
        Validate file extension and size
        
        Args:
            file: UploadFile object from FastAPI
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not file.filename:
            return False, "No filename provided"
        
        # Check file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in self.ALLOWED_EXTENSIONS:
            allowed = ', '.join(self.ALLOWED_EXTENSIONS.keys())
            return False, f"Invalid file type. Allowed types: {allowed}"
        
        # Check MIME type if available
        if file.content_type:
            allowed_mimes = self.ALLOWED_EXTENSIONS[file_ext]
            if file.content_type not in allowed_mimes:
                return False, f"Invalid content type for {file_ext} file"
        
        return True, None
    
    async def save_file(self, file: UploadFile, tenant_id: str) -> Tuple[str, str]:
        """
        Save uploaded file with UUID naming
        
        Args:
            file: UploadFile object from FastAPI
            tenant_id: Tenant ID for organizing files
            
        Returns:
            Tuple of (file_path, original_filename)
            
        Raises:
            HTTPException: If validation fails or file size exceeds limit
        """
        # Validate file
        is_valid, error_msg = self.validate_file(file)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Read file content
        content = await file.read()
        
        # Check file size
        if len(content) > self.MAX_FILE_SIZE:
            size_mb = self.MAX_FILE_SIZE / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds {size_mb}MB limit"
            )
        
        # Generate UUID filename
        file_ext = Path(file.filename).suffix.lower()
        uuid_filename = f"{uuid.uuid4()}{file_ext}"
        
        # Create tenant subdirectory
        tenant_dir = self.upload_dir / tenant_id
        tenant_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = tenant_dir / uuid_filename
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Return relative path from project root
        relative_path = str(file_path.relative_to(Path.cwd()))
        
        return relative_path, file.filename
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from the upload directory
        
        Args:
            file_path: Path to the file to delete
            
        Returns:
            True if file was deleted, False if file didn't exist
        """
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                path.unlink()
                return True
            return False
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")
            return False
    
    def get_file_path(self, file_path: str) -> Optional[Path]:
        """
        Get full path to a file
        
        Args:
            file_path: Relative path to the file
            
        Returns:
            Path object if file exists, None otherwise
        """
        path = Path(file_path)
        if path.exists() and path.is_file():
            return path
        return None
    
    @staticmethod
    def validate_customization_rules(
        is_personalized: bool,
        is_new_client: bool,
        customization_notes: Optional[str],
        attachment_path: Optional[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate business rules for customization
        
        Rules:
        1. If is_personalized is True, customization_notes is MANDATORY
        2. If is_personalized is True AND is_new_client is True, attachment is MANDATORY
        
        Args:
            is_personalized: Whether the item is personalized
            is_new_client: Whether this is a new client
            customization_notes: Customization notes text
            attachment_path: Path to attachment file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        errors = []
        
        # Rule 1: Personalized items require notes
        if is_personalized:
            if not customization_notes or not customization_notes.strip():
                errors.append("Descrição da customização é obrigatória para pedidos personalizados")
        
        # Rule 2: Personalized + New Client requires attachment
        if is_personalized and is_new_client:
            if not attachment_path or not attachment_path.strip():
                errors.append("Anexo é obrigatório para clientes novos em pedidos personalizados")
        
        if errors:
            return False, "; ".join(errors)
        
        return True, None
