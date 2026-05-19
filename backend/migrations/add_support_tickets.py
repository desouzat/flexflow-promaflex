"""
FlexFlow - Database Migration: Add Support Tickets Table
Creates support_tickets table for user support system
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from database import get_database_url

def run_migration():
    """Add support_tickets table to the database"""
    database_url = get_database_url()
    engine = create_engine(database_url)
    
    with engine.begin() as conn:
        try:
            print("\n[1/2] Creating support_tickets table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS support_tickets (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    description TEXT NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP WITH TIME ZONE NULL,
                    CONSTRAINT ck_support_ticket_status CHECK (status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'))
                );
            """))
            print("✓ support_tickets table created")
            
            print("\n[2/2] Creating indexes...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_support_ticket_user_id ON support_tickets(user_id);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_support_ticket_status ON support_tickets(status);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_support_ticket_created_at ON support_tickets(created_at);
            """))
            print("✓ Indexes created")
            
            print("\n✅ Migration completed successfully!")
            print("\nNew Table:")
            print("  • support_tickets (id, user_id, description, status, created_at, updated_at, resolved_at)")
            print("\nSupport System Features:")
            print("  • Users can report problems via UI")
            print("  • Tickets are sent via email to support team")
            print("  • Ticket ID is returned to user for tracking")
            print("  • Status tracking: OPEN → IN_PROGRESS → RESOLVED → CLOSED")
            
        except Exception as e:
            print(f"\n❌ Migration failed: {str(e)}")
            raise

if __name__ == "__main__":
    print("=" * 70)
    print("FlexFlow - Add Support Tickets Migration")
    print("=" * 70)
    run_migration()
