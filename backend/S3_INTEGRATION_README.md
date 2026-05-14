# FlexFlow S3 Integration - Automated Data Pipe

## Overview

The S3 Integration module provides automated data ingestion from S3-compatible cloud storage (AWS S3, Google Cloud Storage, MinIO, etc.). Files uploaded to the configured bucket are automatically detected, downloaded, processed, and moved to a processed folder.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    S3-Compatible Bucket                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Root Folder (New Files)                               │ │
│  │  • pedido_001.xlsx                                     │ │
│  │  • pedido_002.csv                                      │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  /processed (Archived Files)                           │ │
│  │  • 20260514_100000_pedido_001.xlsx                     │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    ┌───────────────┐
                    │  S3 Service   │
                    │  (boto3)      │
                    └───────────────┘
                            ↓
                    ┌───────────────┐
                    │ Import Service│
                    │  (Validation) │
                    └───────────────┘
                            ↓
                    ┌───────────────┐
                    │   Database    │
                    │  (PostgreSQL) │
                    └───────────────┘
```

## Components

### 1. S3Service (`backend/services/s3_service.py`)

Main service for S3 operations:

- **`check_for_new_files()`**: Main method that orchestrates the entire workflow
- **`list_new_files()`**: Lists unprocessed CSV/XLSX files in bucket root
- **`download_file()`**: Downloads a file from S3 to memory
- **`move_to_processed()`**: Moves processed files to `/processed` folder with timestamp
- **`get_default_mapping()`**: Returns default ONET column mapping

### 2. Background Worker (`backend/services/background_worker.py`)

Periodic task runner:

- Runs every **10 minutes** automatically
- Checks S3 bucket for new files
- Processes files using ImportService
- Logs all operations
- Graceful shutdown support

### 3. API Endpoint (`/api/import/sync-s3`)

Manual trigger endpoint:

- Allows users to manually trigger S3 sync
- Returns detailed sync results
- Shows number of files processed and POs imported

### 4. UI Button (Import Page)

**"Sincronizar com ONET (Nuvem)"** button:

- Located in the Import page header
- Triggers manual S3 sync
- Shows success toast with results
- Displays number of new POs found

## Configuration

### Environment Variables (`.env`)

```bash
# S3 Configuration
S3_ACCESS_KEY=your_access_key_here
S3_SECRET_KEY=your_secret_key_here
S3_BUCKET_NAME=your_bucket_name_here
S3_ENDPOINT=https://storage.googleapis.com  # For Google Cloud Storage
```

### For Different Cloud Providers

**Google Cloud Storage:**
```bash
S3_ENDPOINT=https://storage.googleapis.com
```

**AWS S3:**
```bash
S3_ENDPOINT=  # Leave empty or use https://s3.amazonaws.com
```

**MinIO (Self-hosted):**
```bash
S3_ENDPOINT=http://your-minio-server:9000
```

## File Format Requirements

### Supported Formats
- `.xlsx` (Excel 2007+)
- `.xls` (Excel 97-2003)
- `.csv` (Comma-separated values)

### Expected Columns (ONET Format)

| Column Name       | Type    | Description                    |
|-------------------|---------|--------------------------------|
| PO                | String  | Purchase Order number          |
| Cliente           | String  | Client name                    |
| SKU               | String  | Product SKU                    |
| Quantidade        | Integer | Quantity ordered               |
| Preço Unitário    | Decimal | Unit price                     |
| Custo MP          | Decimal | Material cost                  |
| Custo MO          | Decimal | Labor cost                     |
| Custo Energia     | Decimal | Energy cost                    |
| Custo Gás         | Decimal | Gas cost                       |

## Workflow

### Automatic Sync (Every 10 minutes)

1. Background worker wakes up
2. Connects to S3 bucket
3. Lists all CSV/XLSX files in root folder
4. For each file:
   - Downloads to memory
   - Validates with ImportService
   - If valid: Creates PO in database
   - If valid: Moves file to `/processed` folder
   - If invalid: Leaves file in root, logs error
5. Logs summary of sync operation

### Manual Sync (User-triggered)

1. User clicks "Sincronizar com ONET (Nuvem)" button
2. Frontend calls `/api/import/sync-s3` endpoint
3. Same workflow as automatic sync
4. Returns results to UI
5. Shows toast notification with results

## Error Handling

### Configuration Errors
- If S3 credentials are missing: Returns 503 Service Unavailable
- If bucket doesn't exist: Logs error, continues operation

### File Processing Errors
- Invalid file format: Skips file, logs error
- Validation errors: Leaves file in bucket, logs detailed errors
- Network errors: Retries on next sync cycle

### Database Errors
- Transaction rollback on failure
- File remains in bucket for retry
- Error logged for investigation

## Testing

### Mock Test Script

Run the mock integration test:

```bash
# Set PYTHONPATH and run test
set PYTHONPATH=%CD%
python backend/tests/test_s3_integration.py
```

### Test Coverage

- S3 service initialization
- File listing and filtering
- File download
- File movement to processed folder
- Complete workflow simulation
- Error scenarios

## Installation

### 1. Install boto3

```bash
pip install boto3==1.34.0
```

Or update requirements:

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Credentials

Edit `backend/.env`:

```bash
S3_ACCESS_KEY=your_actual_key
S3_SECRET_KEY=your_actual_secret
S3_BUCKET_NAME=flexflow-onet-imports
S3_ENDPOINT=https://storage.googleapis.com
```

### 3. Start Application

The background worker starts automatically with the FastAPI application:

```bash
cd backend
uvicorn main:app --reload
```

## Monitoring

### Logs

All S3 operations are logged:

```
[INFO] Starting S3 sync background task
[INFO] Running scheduled S3 sync...
[INFO] Found 2 unprocessed files in bucket
[INFO] Processing file: pedido_001.xlsx
[INFO] Successfully processed pedido_001.xlsx: PO PO-2026-001
[INFO] S3 sync completed: 2 files processed, 0 failed
```

### Manual Check

Use the UI button to manually trigger sync and see results in real-time.

## Security Considerations

1. **Credentials**: Store S3 credentials securely in `.env` file
2. **Access Control**: Use IAM roles with minimal permissions
3. **Bucket Policy**: Restrict bucket access to specific IPs if possible
4. **File Validation**: All files are validated before processing
5. **Multi-tenancy**: Files are associated with correct tenant

## Troubleshooting

### "S3 service not configured"
- Check that all environment variables are set in `.env`
- Restart the application after updating `.env`

### "Failed to list files from S3"
- Verify bucket name is correct
- Check access key has `s3:ListBucket` permission
- Verify endpoint URL is correct for your provider

### "Failed to download file"
- Check access key has `s3:GetObject` permission
- Verify file exists in bucket
- Check network connectivity

### Files not being processed
- Check file format (must be .csv, .xlsx, or .xls)
- Verify file is in bucket root (not in subfolder)
- Check application logs for validation errors

## Future Enhancements

- [ ] Support for multiple bucket monitoring
- [ ] Configurable sync interval
- [ ] Email notifications on sync failures
- [ ] Dashboard widget showing sync status
- [ ] Support for custom column mappings per client
- [ ] Automatic retry with exponential backoff
- [ ] File archival to cold storage after X days

## API Reference

### POST `/api/import/sync-s3`

Manually trigger S3 synchronization.

**Authentication:** Required (JWT token)

**Response:**
```json
{
  "success": true,
  "message": "Sincronização concluída: 2 arquivo(s) processado(s)",
  "files_found": 2,
  "files_processed": 2,
  "files_failed": 0,
  "pos_imported": ["PO-2026-001", "PO-2026-002"],
  "errors": []
}
```

## Support

For issues or questions:
1. Check application logs
2. Verify S3 configuration
3. Run mock test script
4. Contact system administrator
