import sys
import os
from pathlib import Path
from sqlalchemy import text

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from database import engine

def add_columns():
    with engine.connect() as conn:
        print("[DEBUG] Conectado ao banco de dados.")
        
        # Check if column sla_paused_at exists
        res = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='purchase_orders' AND column_name='sla_paused_at'"
        )).fetchone()
        
        if not res:
            print("[INFO] Adicionando coluna 'sla_paused_at' a 'purchase_orders'...")
            conn.execute(text("ALTER TABLE purchase_orders ADD COLUMN sla_paused_at TIMESTAMP WITH TIME ZONE;"))
            print("[SUCCESS] Coluna 'sla_paused_at' adicionada.")
        else:
            print("[INFO] Coluna 'sla_paused_at' já existe.")
            
        # Check if column total_hold_time_seconds exists
        res = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='purchase_orders' AND column_name='total_hold_time_seconds'"
        )).fetchone()
        
        if not res:
            print("[INFO] Adicionando coluna 'total_hold_time_seconds' a 'purchase_orders'...")
            conn.execute(text("ALTER TABLE purchase_orders ADD COLUMN total_hold_time_seconds INTEGER DEFAULT 0 NOT NULL;"))
            print("[SUCCESS] Coluna 'total_hold_time_seconds' adicionada.")
        else:
            print("[INFO] Coluna 'total_hold_time_seconds' já existe.")
            
        # Commit transaction
        conn.commit()
        print("[SUCCESS] Banco de dados atualizado com sucesso!")

if __name__ == "__main__":
    add_columns()
