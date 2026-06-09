import sys
import os
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Add project root directory to path to import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import engine

def nuke_database():
    print("=" * 60)
    print("⚠️  DATABASE FORCE NUKE ACTIVE (CLEAN SLATE)")
    print("=" * 60)
    
    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            try:
                print("[INFO] Attempting to drop and recreate public schema...")
                conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
                conn.execute(text("CREATE SCHEMA public;"))
                conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
                conn.execute(text("GRANT ALL ON SCHEMA public TO flexflow_app;"))
                print("[SUCCESS] Public schema dropped and recreated successfully.")
                trans.commit()
            except SQLAlchemyError as e:
                trans.rollback()
                print(f"[WARNING] Recreating schema failed: {e}. Falling back to dynamic table drop...")
                
                # Start new transaction for fallback table drop
                trans_fallback = conn.begin()
                try:
                    # Query all tables in public schema
                    result = conn.execute(text("""
                        SELECT tablename FROM pg_tables WHERE schemaname = 'public';
                    """))
                    tables = [row[0] for row in result.fetchall()]
                    print(f"[INFO] Found tables to drop: {tables}")
                    
                    for table in tables:
                        print(f"  Dropping table: {table} CASCADE...")
                        conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE;'))
                        
                    trans_fallback.commit()
                    print("[SUCCESS] All tables dropped via fallback successfully.")
                except SQLAlchemyError as err:
                    trans_fallback.rollback()
                    print(f"[ERROR] Fallback drop failed: {err}")
                    raise err
        
        print("\n" + "=" * 60)
        print("DATABASE NUKED SUCCESSFULLY")
        print("=" * 60)
        sys.exit(0)
        
    except Exception as e:
        print(f"[FATAL] Database force nuke failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    nuke_database()
