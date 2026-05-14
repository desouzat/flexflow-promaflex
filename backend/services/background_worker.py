"""
FlexFlow Background Worker
Handles periodic tasks like S3 synchronization.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.services.s3_service import S3Service

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """
    Background worker for periodic tasks.
    
    Features:
    - Runs S3 sync every 10 minutes
    - Graceful shutdown support
    - Error handling and logging
    """
    
    def __init__(self):
        """Initialize background worker."""
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.sync_interval = 600  # 10 minutes in seconds
        
        # System user ID for automated imports (use a fixed UUID)
        # In production, this should be a real system user in the database
        self.system_user_id = "00000000-0000-0000-0000-000000000000"
        self.system_tenant_id = "00000000-0000-0000-0000-000000000000"
    
    async def sync_s3_task(self):
        """
        Periodic task to check S3 for new files.
        
        Runs every 10 minutes and processes any new files found.
        """
        logger.info("Starting S3 sync background task")
        
        while self.running:
            try:
                # Get database session
                db: Session = SessionLocal()
                
                try:
                    # Create S3 service
                    s3_service = S3Service(db)
                    
                    # Check if S3 is configured
                    if not s3_service.is_configured():
                        logger.warning("S3 service not configured. Skipping sync.")
                    else:
                        logger.info("Running scheduled S3 sync...")
                        
                        try:
                            # Check for new files (wrapped to prevent blocking)
                            result = s3_service.check_for_new_files(
                                tenant_id=self.system_tenant_id,
                                user_id=self.system_user_id
                            )
                            
                            # Log results
                            if result['success']:
                                if result['files_processed'] > 0:
                                    logger.info(
                                        f"S3 sync completed: {result['files_processed']} files processed, "
                                        f"{result['files_failed']} failed. "
                                        f"POs imported: {', '.join(result['pos_imported'])}"
                                    )
                                else:
                                    logger.info("S3 sync completed: No new files found")
                            else:
                                logger.error(f"S3 sync failed: {'; '.join(result['errors'])}")
                        except Exception as s3_error:
                            # Log S3 errors but don't crash the worker
                            logger.error(f"S3 sync error (non-blocking): {str(s3_error)}")
                            print(f"[WARNING] S3 sync error: {str(s3_error)}")
                
                finally:
                    db.close()
            
            except Exception as e:
                logger.error(f"Error in S3 sync task: {str(e)}", exc_info=True)
                print(f"[WARNING] Background worker error: {str(e)}")
            
            # Wait for next interval
            await asyncio.sleep(self.sync_interval)
        
        logger.info("S3 sync background task stopped")
    
    async def start(self):
        """
        Start the background worker.
        
        This should be called when the FastAPI application starts.
        """
        if self.running:
            logger.warning("Background worker already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self.sync_s3_task())
        logger.info("Background worker started")
    
    async def stop(self):
        """
        Stop the background worker gracefully.
        
        This should be called when the FastAPI application shuts down.
        """
        if not self.running:
            return
        
        logger.info("Stopping background worker...")
        self.running = False
        
        if self.task:
            # Wait for current task to finish (with timeout)
            try:
                await asyncio.wait_for(self.task, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning("Background worker did not stop gracefully, cancelling...")
                self.task.cancel()
        
        logger.info("Background worker stopped")


# Global worker instance
background_worker = BackgroundWorker()


async def start_background_worker():
    """Start the background worker. Called on app startup."""
    await background_worker.start()


async def stop_background_worker():
    """Stop the background worker. Called on app shutdown."""
    await background_worker.stop()
