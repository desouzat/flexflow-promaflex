"""
Migration: Add Staging Area fields to OrderItem
Adds: is_personalized, is_new_client, customization_notes, attachment_path
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from backend.database import engine


def upgrade():
    """Add staging area fields to order_items table"""
    
    with engine.connect() as conn:
        # Add is_personalized column
        conn.execute(text("""
            ALTER TABLE order_items 
            ADD COLUMN IF NOT EXISTS is_personalized BOOLEAN NOT NULL DEFAULT FALSE
        """))
        
        # Add is_new_client column
        conn.execute(text("""
            ALTER TABLE order_items 
            ADD COLUMN IF NOT EXISTS is_new_client BOOLEAN NOT NULL DEFAULT FALSE
        """))
        
        # Add customization_notes column
        conn.execute(text("""
            ALTER TABLE order_items 
            ADD COLUMN IF NOT EXISTS customization_notes TEXT
        """))
        
        # Add attachment_path column
        conn.execute(text("""
            ALTER TABLE order_items 
            ADD COLUMN IF NOT EXISTS attachment_path VARCHAR(500)
        """))
        
        conn.commit()
        print("[SUCCESS] Successfully added staging area fields to order_items table")


def downgrade():
    """Remove staging area fields from order_items table"""
    
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE order_items DROP COLUMN IF EXISTS is_personalized"))
        conn.execute(text("ALTER TABLE order_items DROP COLUMN IF EXISTS is_new_client"))
        conn.execute(text("ALTER TABLE order_items DROP COLUMN IF EXISTS customization_notes"))
        conn.execute(text("ALTER TABLE order_items DROP COLUMN IF EXISTS attachment_path"))
        conn.commit()
        print("[SUCCESS] Successfully removed staging area fields from order_items table")


if __name__ == "__main__":
    print("Running migration: Add Staging Area fields...")
    upgrade()
