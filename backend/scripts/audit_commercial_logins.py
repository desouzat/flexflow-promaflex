import sys
import os
import socket
import subprocess
import time

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

def is_port_open(port=5434):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.5)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

def ensure_cloud_sql_proxy():
    if is_port_open(5434):
        return None

    proxy_binary = os.path.join(os.path.dirname(__file__), "../cloud-sql-proxy.exe")
    if not os.path.exists(proxy_binary):
        return None

    gcloud_cmd = r"C:\Users\Thiago\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    try:
        token_out = subprocess.check_output([gcloud_cmd, 'auth', 'print-access-token'], stderr=subprocess.STDOUT)
        token = token_out.decode().strip()
        
        proc = subprocess.Popen([
            proxy_binary,
            'flexflow-promaflex:southamerica-east1:flexflow-db-v1',
            '--port', '5434',
            '--token', token
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3.5)
        return proc
    except Exception as err:
        print(f"[WARNING] Could not start Cloud SQL Proxy: {err}")
        return None

proxy_proc = ensure_cloud_sql_proxy()

from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import User

db: Session = SessionLocal()
try:
    print("=" * 80)
    print("📋 RELATÓRIO DE AUDITORIA DE USUÁRIOS - TIME COMERCIAL (FLEXFLOW)")
    print("=" * 80)
    
    # 1. Todos os usuários da área Comercial
    commercial_users = db.query(User).filter(
        (User.area.ilike("%comercial%")) | 
        (User.email.ilike("%comercial%"))
    ).order_by(User.name).all()
    
    print(f"\nTotal de usuários encontrados no Comercial: {len(commercial_users)}\n")
    print(f"{'NOME':<30} | {'E-MAIL (LOGIN)':<35} | {'ROLE':<10} | {'SENHA?':<8} | {'CANCEL?'}")
    print("-" * 95)
    
    for u in commercial_users:
        # Check if password hash exists without printing it
        pwd_hash = getattr(u, 'hashed_password', None) or getattr(u, 'password_hash', None)
        has_pwd = "SIM" if pwd_hash and len(str(pwd_hash)) > 10 else "NÃO"
        can_cancel = "SIM" if getattr(u, 'can_cancel_commercial', False) else "NÃO"
        
        name_str = (u.name or "N/A")[:30]
        email_str = (u.email or "N/A")[:35]
        role_str = (u.role or "N/A")[:10]
        
        print(f"{name_str:<30} | {email_str:<35} | {role_str:<10} | {has_pwd:<8} | {can_cancel}")
        
    print("\n" + "=" * 80)
    print("🔍 DIAGNÓSTICO ESPECÍFICO: CESAR E ALAN")
    print("=" * 80)
    
    targets = db.query(User).filter(
        (User.name.ilike("%cesar%")) | 
        (User.email.ilike("%cesar%")) | 
        (User.name.ilike("%alan%")) | 
        (User.email.ilike("%alan%"))
    ).all()
    
    if targets:
        print(f"Encontrados {len(targets)} registro(s) correspondente(s):")
        for t in targets:
            pwd_hash = getattr(t, 'hashed_password', None) or getattr(t, 'password_hash', None)
            has_pwd = "SIM" if pwd_hash and len(str(pwd_hash)) > 10 else "NÃO"
            print(f"  - ID: {t.id}")
            print(f"    Nome: {t.name}")
            print(f"    E-mail (Login): {t.email}")
            print(f"    Área: {t.area} | Role: {t.role}")
            print(f"    Senha configurada no banco? {has_pwd}")
            print(f"    Permissão Cancelamento Comercial? {getattr(t, 'can_cancel_commercial', False)}")
            print("-" * 50)
    else:
        print("⚠️ ALERTA: Nenhum usuário contendo 'Cesar' ou 'Alan' foi encontrado na base de dados!")
        
except Exception as e:
    print(f"ERRO durante auditoria: {e}")
finally:
    db.close()
    if proxy_proc:
        proxy_proc.terminate()
