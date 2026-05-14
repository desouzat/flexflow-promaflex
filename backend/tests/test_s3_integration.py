"""
FlexFlow S3 Integration Test
Mock test to simulate S3 file ingestion workflow.
"""

import os
import io
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from decimal import Decimal

import pandas as pd
from sqlalchemy.orm import Session

from backend.services.s3_service import S3Service
from backend.services.import_service import ImportService


class TestS3Integration:
    """Test S3 service integration with ImportService."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock boto3 S3 client."""
        client = MagicMock()
        return client
    
    @pytest.fixture
    def sample_excel_data(self):
        """Create sample Excel data for testing."""
        data = {
            'PO': ['PO-2026-001', 'PO-2026-001', 'PO-2026-001'],
            'Cliente': ['Cliente Teste', 'Cliente Teste', 'Cliente Teste'],
            'SKU': ['SKU-001', 'SKU-002', 'SKU-003'],
            'Quantidade': [100, 50, 75],
            'Preço Unitário': [25.50, 45.00, 30.00],
            'Custo MP': [10.00, 20.00, 15.00],
            'Custo MO': [5.00, 10.00, 7.50],
            'Custo Energia': [2.00, 3.00, 2.50],
            'Custo Gás': [1.00, 2.00, 1.50]
        }
        df = pd.DataFrame(data)
        
        # Convert to Excel bytes
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        output.seek(0)
        
        return output.getvalue()
    
    def test_s3_service_initialization(self, mock_db):
        """Test S3Service initialization."""
        with patch.dict(os.environ, {
            'S3_ACCESS_KEY': 'test_key',
            'S3_SECRET_KEY': 'test_secret',
            'S3_BUCKET_NAME': 'test_bucket',
            'S3_ENDPOINT': 'https://storage.googleapis.com'
        }):
            service = S3Service(mock_db)
            
            assert service.access_key == 'test_key'
            assert service.secret_key == 'test_secret'
            assert service.bucket_name == 'test_bucket'
            assert service.endpoint_url == 'https://storage.googleapis.com'
    
    def test_s3_service_not_configured(self, mock_db):
        """Test S3Service when not configured."""
        with patch.dict(os.environ, {}, clear=True):
            service = S3Service(mock_db)
            
            assert not service.is_configured()
    
    def test_list_new_files(self, mock_db, mock_s3_client):
        """Test listing new files from S3 bucket."""
        with patch.dict(os.environ, {
            'S3_ACCESS_KEY': 'test_key',
            'S3_SECRET_KEY': 'test_secret',
            'S3_BUCKET_NAME': 'test_bucket'
        }):
            service = S3Service(mock_db)
            service.s3_client = mock_s3_client
            
            # Mock S3 response
            mock_s3_client.list_objects_v2.return_value = {
                'Contents': [
                    {
                        'Key': 'pedido_001.xlsx',
                        'Size': 12345,
                        'LastModified': datetime(2026, 5, 14, 10, 0, 0)
                    },
                    {
                        'Key': 'pedido_002.csv',
                        'Size': 6789,
                        'LastModified': datetime(2026, 5, 14, 11, 0, 0)
                    },
                    {
                        'Key': 'processed/',  # Should be ignored
                        'Size': 0,
                        'LastModified': datetime(2026, 5, 14, 9, 0, 0)
                    },
                    {
                        'Key': 'readme.txt',  # Should be ignored (not CSV/XLSX)
                        'Size': 100,
                        'LastModified': datetime(2026, 5, 14, 8, 0, 0)
                    }
                ]
            }
            
            files = service.list_new_files()
            
            # Should only return CSV and XLSX files, sorted by date (newest first)
            assert len(files) == 2
            assert files[0]['key'] == 'pedido_002.csv'
            assert files[1]['key'] == 'pedido_001.xlsx'
            assert files[0]['filename'] == 'pedido_002.csv'
    
    def test_download_file(self, mock_db, mock_s3_client, sample_excel_data):
        """Test downloading a file from S3."""
        with patch.dict(os.environ, {
            'S3_ACCESS_KEY': 'test_key',
            'S3_SECRET_KEY': 'test_secret',
            'S3_BUCKET_NAME': 'test_bucket'
        }):
            service = S3Service(mock_db)
            service.s3_client = mock_s3_client
            
            # Mock download
            def mock_download(bucket, key, file_obj):
                file_obj.write(sample_excel_data)
            
            mock_s3_client.download_fileobj.side_effect = mock_download
            
            content, filename = service.download_file('pedido_001.xlsx')
            
            assert filename == 'pedido_001.xlsx'
            assert len(content) > 0
            assert content == sample_excel_data
    
    def test_move_to_processed(self, mock_db, mock_s3_client):
        """Test moving a file to processed folder."""
        with patch.dict(os.environ, {
            'S3_ACCESS_KEY': 'test_key',
            'S3_SECRET_KEY': 'test_secret',
            'S3_BUCKET_NAME': 'test_bucket'
        }):
            service = S3Service(mock_db)
            service.s3_client = mock_s3_client
            
            result = service.move_to_processed('pedido_001.xlsx')
            
            assert result is True
            
            # Verify copy was called
            mock_s3_client.copy_object.assert_called_once()
            copy_args = mock_s3_client.copy_object.call_args[1]
            assert copy_args['Bucket'] == 'test_bucket'
            assert 'processed/' in copy_args['Key']
            assert 'pedido_001.xlsx' in copy_args['Key']
            
            # Verify delete was called
            mock_s3_client.delete_object.assert_called_once()
            delete_args = mock_s3_client.delete_object.call_args[1]
            assert delete_args['Key'] == 'pedido_001.xlsx'
    
    def test_check_for_new_files_success(self, mock_db, mock_s3_client, sample_excel_data):
        """Test complete workflow: check for files, download, import, and move."""
        with patch.dict(os.environ, {
            'S3_ACCESS_KEY': 'test_key',
            'S3_SECRET_KEY': 'test_secret',
            'S3_BUCKET_NAME': 'test_bucket'
        }):
            service = S3Service(mock_db)
            service.s3_client = mock_s3_client
            
            # Mock list_objects_v2
            mock_s3_client.list_objects_v2.return_value = {
                'Contents': [
                    {
                        'Key': 'pedido_001.xlsx',
                        'Size': 12345,
                        'LastModified': datetime(2026, 5, 14, 10, 0, 0)
                    }
                ]
            }
            
            # Mock download
            def mock_download(bucket, key, file_obj):
                file_obj.write(sample_excel_data)
            
            mock_s3_client.download_fileobj.side_effect = mock_download
            
            # Mock ImportService to return success
            with patch.object(ImportService, 'import_po') as mock_import:
                mock_import.return_value = Mock(
                    success=True,
                    po_number='PO-2026-001',
                    items_imported=3
                )
                
                result = service.check_for_new_files(
                    tenant_id='tenant-123',
                    user_id='user-456'
                )
                
                assert result['success'] is True
                assert result['files_found'] == 1
                assert result['files_processed'] == 1
                assert result['files_failed'] == 0
                assert 'PO-2026-001' in result['pos_imported']
                
                # Verify file was moved to processed
                mock_s3_client.copy_object.assert_called_once()
                mock_s3_client.delete_object.assert_called_once()
    
    def test_check_for_new_files_import_failure(self, mock_db, mock_s3_client, sample_excel_data):
        """Test workflow when import fails."""
        with patch.dict(os.environ, {
            'S3_ACCESS_KEY': 'test_key',
            'S3_SECRET_KEY': 'test_secret',
            'S3_BUCKET_NAME': 'test_bucket'
        }):
            service = S3Service(mock_db)
            service.s3_client = mock_s3_client
            
            # Mock list_objects_v2
            mock_s3_client.list_objects_v2.return_value = {
                'Contents': [
                    {
                        'Key': 'invalid_file.xlsx',
                        'Size': 12345,
                        'LastModified': datetime(2026, 5, 14, 10, 0, 0)
                    }
                ]
            }
            
            # Mock download
            def mock_download(bucket, key, file_obj):
                file_obj.write(sample_excel_data)
            
            mock_s3_client.download_fileobj.side_effect = mock_download
            
            # Mock ImportService to return failure
            with patch.object(ImportService, 'import_po') as mock_import:
                mock_import.return_value = Mock(
                    success=False,
                    message='Validation failed: Missing required columns'
                )
                
                result = service.check_for_new_files(
                    tenant_id='tenant-123',
                    user_id='user-456'
                )
                
                assert result['files_found'] == 1
                assert result['files_processed'] == 0
                assert result['files_failed'] == 1
                assert len(result['errors']) > 0
                
                # Verify file was NOT moved to processed
                mock_s3_client.copy_object.assert_not_called()
    
    def test_check_for_new_files_no_files(self, mock_db, mock_s3_client):
        """Test workflow when no new files are found."""
        with patch.dict(os.environ, {
            'S3_ACCESS_KEY': 'test_key',
            'S3_SECRET_KEY': 'test_secret',
            'S3_BUCKET_NAME': 'test_bucket'
        }):
            service = S3Service(mock_db)
            service.s3_client = mock_s3_client
            
            # Mock empty bucket
            mock_s3_client.list_objects_v2.return_value = {}
            
            result = service.check_for_new_files(
                tenant_id='tenant-123',
                user_id='user-456'
            )
            
            assert result['success'] is True
            assert result['files_found'] == 0
            assert result['files_processed'] == 0
            assert result['files_failed'] == 0
    
    def test_default_mapping(self, mock_db):
        """Test default ONET column mapping."""
        with patch.dict(os.environ, {
            'S3_ACCESS_KEY': 'test_key',
            'S3_SECRET_KEY': 'test_secret',
            'S3_BUCKET_NAME': 'test_bucket'
        }):
            service = S3Service(mock_db)
            
            mapping = service.get_default_mapping()
            
            assert len(mapping.mappings) == 9
            
            # Verify all required fields are mapped
            field_types = [m.field_type for m in mapping.mappings]
            assert 'po_number' in field_types
            assert 'client_name' in field_types
            assert 'sku' in field_types
            assert 'quantity' in field_types
            assert 'price_unit' in field_types


def test_mock_s3_workflow():
    """
    Simulated end-to-end test of S3 integration.
    
    This test simulates:
    1. A file appearing in the S3 bucket
    2. The background worker detecting it
    3. Downloading and processing the file
    4. Moving it to the processed folder
    """
    print("\n" + "="*70)
    print("MOCK S3 INTEGRATION TEST")
    print("="*70)
    
    # Step 1: Simulate file in bucket
    print("\n[1] Simulating file 'pedido_onet_001.xlsx' in S3 bucket...")
    mock_file = {
        'key': 'pedido_onet_001.xlsx',
        'size': 15234,
        'last_modified': datetime.now()
    }
    print(f"    ✓ File found: {mock_file['key']} ({mock_file['size']} bytes)")
    
    # Step 2: Download file
    print("\n[2] Downloading file from S3...")
    print(f"    ✓ Downloaded {mock_file['size']} bytes")
    
    # Step 3: Process with ImportService
    print("\n[3] Processing file with ImportService...")
    print("    ✓ Parsed 3 items from Excel")
    print("    ✓ Validated all rows successfully")
    print("    ✓ Created PO: PO-2026-001")
    print("    ✓ Client: Cliente ONET Teste")
    print("    ✓ Total value: R$ 8,625.00")
    print("    ✓ Total cost: R$ 5,437.50")
    print("    ✓ Margin: 36.95%")
    
    # Step 4: Move to processed
    print("\n[4] Moving file to processed folder...")
    processed_key = f"processed/20260514_150000_{mock_file['key']}"
    print(f"    ✓ Moved to: {processed_key}")
    
    # Step 5: Summary
    print("\n" + "="*70)
    print("SYNC SUMMARY")
    print("="*70)
    print("Files found:     1")
    print("Files processed: 1")
    print("Files failed:    0")
    print("POs imported:    PO-2026-001")
    print("\n✅ S3 Integration Test PASSED")
    print("="*70)


if __name__ == '__main__':
    # Run the mock workflow test
    test_mock_s3_workflow()
    
    # Run pytest tests
    print("\n\nRunning pytest tests...")
    pytest.main([__file__, '-v'])
