"""
FlexFlow S3 Service
Handles automated data ingestion from S3-compatible cloud storage (Google Cloud Storage).
"""

import os
import io
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from sqlalchemy.orm import Session

from backend.services.import_service import ImportService
from backend.schemas.import_schema import ImportMapping, ImportFieldMapping, ImportFieldType, ImportRequest

logger = logging.getLogger(__name__)


class S3Service:
    """
    Service for automated PO import from S3-compatible storage.
    
    Features:
    - Connects to S3-compatible buckets (AWS S3, Google Cloud Storage, MinIO, etc.)
    - Downloads latest CSV/XLSX files
    - Triggers ImportService for processing
    - Moves processed files to /processed folder to avoid duplicates
    - Supports manual and automatic synchronization
    """
    
    def __init__(self, db: Session):
        """
        Initialize S3 service with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.import_service = ImportService(db)
        
        # Load S3 configuration from environment
        self.access_key = os.getenv('S3_ACCESS_KEY')
        self.secret_key = os.getenv('S3_SECRET_KEY')
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
        self.endpoint_url = os.getenv('S3_ENDPOINT')  # For GCS or custom endpoints
        
        # Initialize S3 client
        self.s3_client = None
        if self.access_key and self.secret_key and self.bucket_name:
            try:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    endpoint_url=self.endpoint_url if self.endpoint_url else None
                )
                logger.info(f"S3 client initialized for bucket: {self.bucket_name}")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {str(e)}")
    
    def is_configured(self) -> bool:
        """
        Check if S3 service is properly configured.
        
        Returns:
            True if all required credentials are present
        """
        return all([
            self.access_key,
            self.secret_key,
            self.bucket_name,
            self.s3_client is not None
        ])
    
    def list_new_files(self) -> List[Dict[str, any]]:
        """
        List all unprocessed CSV/XLSX files in the bucket root.
        
        Returns:
            List of file metadata dictionaries with keys: key, size, last_modified
            
        Raises:
            Exception: If S3 connection fails
        """
        if not self.is_configured():
            raise Exception("S3 service is not properly configured. Check environment variables.")
        
        try:
            # List objects in bucket root (not in /processed folder)
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='',  # Root level
                Delimiter='/'  # Don't recurse into folders
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    
                    # Skip folders and processed files
                    if key.endswith('/') or key.startswith('processed/'):
                        continue
                    
                    # Only include CSV and XLSX files
                    if key.lower().endswith(('.csv', '.xlsx', '.xls')):
                        files.append({
                            'key': key,
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'filename': Path(key).name
                        })
            
            # Sort by last modified (newest first)
            files.sort(key=lambda x: x['last_modified'], reverse=True)
            
            logger.info(f"Found {len(files)} unprocessed files in bucket")
            return files
        
        except ClientError as e:
            logger.error(f"S3 ClientError: {str(e)}")
            raise Exception(f"Failed to list files from S3: {str(e)}")
        except NoCredentialsError:
            logger.error("S3 credentials not found")
            raise Exception("S3 credentials not found or invalid")
    
    def download_file(self, file_key: str) -> Tuple[bytes, str]:
        """
        Download a file from S3 bucket.
        
        Args:
            file_key: S3 object key (file path in bucket)
            
        Returns:
            Tuple of (file_content_bytes, filename)
            
        Raises:
            Exception: If download fails
        """
        if not self.is_configured():
            raise Exception("S3 service is not properly configured")
        
        try:
            logger.info(f"Downloading file: {file_key}")
            
            # Download file to memory
            file_obj = io.BytesIO()
            self.s3_client.download_fileobj(self.bucket_name, file_key, file_obj)
            file_obj.seek(0)
            
            content = file_obj.read()
            filename = Path(file_key).name
            
            logger.info(f"Successfully downloaded {filename} ({len(content)} bytes)")
            return content, filename
        
        except ClientError as e:
            logger.error(f"Failed to download {file_key}: {str(e)}")
            raise Exception(f"Failed to download file from S3: {str(e)}")
    
    def move_to_processed(self, file_key: str) -> bool:
        """
        Move a file to the /processed folder in the bucket.
        
        Args:
            file_key: S3 object key (file path in bucket)
            
        Returns:
            True if successful
            
        Raises:
            Exception: If move operation fails
        """
        if not self.is_configured():
            raise Exception("S3 service is not properly configured")
        
        try:
            # Create new key in processed folder with timestamp
            filename = Path(file_key).name
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            new_key = f"processed/{timestamp}_{filename}"
            
            logger.info(f"Moving {file_key} to {new_key}")
            
            # Copy to new location
            self.s3_client.copy_object(
                Bucket=self.bucket_name,
                CopySource={'Bucket': self.bucket_name, 'Key': file_key},
                Key=new_key
            )
            
            # Delete original
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            
            logger.info(f"Successfully moved {file_key} to processed folder")
            return True
        
        except ClientError as e:
            logger.error(f"Failed to move {file_key}: {str(e)}")
            raise Exception(f"Failed to move file to processed folder: {str(e)}")
    
    def get_default_mapping(self) -> ImportMapping:
        """
        Get default column mapping for ONET files.
        
        This assumes a standard ONET format. Adjust mappings as needed.
        
        Returns:
            ImportMapping with default field mappings
        """
        return ImportMapping(
            mappings=[
                ImportFieldMapping(column_name="PO", field_type=ImportFieldType.PO_NUMBER),
                ImportFieldMapping(column_name="Cliente", field_type=ImportFieldType.CLIENT_NAME),
                ImportFieldMapping(column_name="SKU", field_type=ImportFieldType.SKU),
                ImportFieldMapping(column_name="Quantidade", field_type=ImportFieldType.QUANTITY),
                ImportFieldMapping(column_name="Preço Unitário", field_type=ImportFieldType.PRICE_UNIT),
                ImportFieldMapping(column_name="Custo MP", field_type=ImportFieldType.COST_MP),
                ImportFieldMapping(column_name="Custo MO", field_type=ImportFieldType.COST_MO),
                ImportFieldMapping(column_name="Custo Energia", field_type=ImportFieldType.COST_ENERGY),
                ImportFieldMapping(column_name="Custo Gás", field_type=ImportFieldType.COST_GAS),
            ]
        )
    
    def check_for_new_files(self, tenant_id: str, user_id: str) -> Dict[str, any]:
        """
        Check for new files in S3 bucket and process them.
        
        This is the main method called by the background worker or manual trigger.
        
        Args:
            tenant_id: Tenant UUID for multi-tenancy
            user_id: User UUID who triggered the sync (or system user for automatic)
            
        Returns:
            Dictionary with sync results:
            {
                'success': bool,
                'files_found': int,
                'files_processed': int,
                'files_failed': int,
                'pos_imported': List[str],
                'errors': List[str]
            }
        """
        result = {
            'success': True,
            'files_found': 0,
            'files_processed': 0,
            'files_failed': 0,
            'pos_imported': [],
            'errors': []
        }
        
        try:
            # Check configuration
            if not self.is_configured():
                result['success'] = False
                result['errors'].append("S3 service not configured. Check environment variables.")
                return result
            
            # List new files
            files = self.list_new_files()
            result['files_found'] = len(files)
            
            if not files:
                logger.info("No new files found in S3 bucket")
                return result
            
            # Process each file
            for file_info in files:
                file_key = file_info['key']
                filename = file_info['filename']
                
                try:
                    logger.info(f"Processing file: {filename}")
                    
                    # Download file
                    file_content, _ = self.download_file(file_key)
                    
                    # Create import request
                    import_request = ImportRequest(
                        file_content=file_content,
                        file_name=filename,
                        mapping=self.get_default_mapping(),
                        tenant_id=tenant_id,
                        user_id=user_id
                    )
                    
                    # Process with ImportService
                    import_response = self.import_service.import_po(import_request)
                    
                    if import_response.success:
                        # Move to processed folder
                        self.move_to_processed(file_key)
                        
                        result['files_processed'] += 1
                        result['pos_imported'].append(import_response.po_number)
                        logger.info(f"Successfully processed {filename}: PO {import_response.po_number}")
                    else:
                        result['files_failed'] += 1
                        error_msg = f"{filename}: {import_response.message}"
                        result['errors'].append(error_msg)
                        logger.error(f"Failed to process {filename}: {import_response.message}")
                
                except Exception as e:
                    result['files_failed'] += 1
                    error_msg = f"{filename}: {str(e)}"
                    result['errors'].append(error_msg)
                    logger.error(f"Error processing {filename}: {str(e)}")
            
            # Set overall success based on results
            if result['files_failed'] > 0 and result['files_processed'] == 0:
                result['success'] = False
            
            return result
        
        except Exception as e:
            logger.error(f"Error in check_for_new_files: {str(e)}")
            result['success'] = False
            result['errors'].append(f"Sync error: {str(e)}")
            return result
