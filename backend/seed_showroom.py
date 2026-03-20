"""
FlexFlow - Script de Seed para Showroom do Kickoff
Insere 8 pedidos demo diretamente no banco de dados usando WorkflowService
"""

import sys
import os
from datetime import datetime
from decimal import Decimal

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Adiciona o diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine
from backend.models import Tenant, User, PurchaseOrder, OrderItem
from backend.middleware import RequestContext


# Dados dos pedidos demo (mesmos da planilha)
DEMO_ORDERS = [
    {
        'po_number': 'PO-2024-001',
        'client_name': 'Acme Corp',
        'items': [
            {'sku': 'FLEX-1000', 'quantity': 100, 'price': Decimal('150.00'), 'cost_mp': Decimal('80.00'), 
             'cost_mo': Decimal('25.00'), 'cost_energy': Decimal('8.00'), 'cost_gas': Decimal('5.00'), 'is_custom': True},
            {'sku': 'FLEX-2000', 'quantity': 50, 'price': Decimal('280.00'), 'cost_mp': Decimal('150.00'), 
             'cost_mo': Decimal('45.00'), 'cost_energy': Decimal('12.00'), 'cost_gas': Decimal('8.00'), 'is_custom': False},
        ]
    },
    {
        'po_number': 'PO-2024-002',
        'client_name': 'Beta Industries',
        'items': [
            {'sku': 'FLEX-3000', 'quantity': 75, 'price': Decimal('420.00'), 'cost_mp': Decimal('220.00'), 
             'cost_mo': Decimal('70.00'), 'cost_energy': Decimal('18.00'), 'cost_gas': Decimal('12.00'), 'is_custom': False},
            {'sku': 'FLEX-CUSTOM-A', 'quantity': 25, 'price': Decimal('650.00'), 'cost_mp': Decimal('350.00'), 
             'cost_mo': Decimal('110.00'), 'cost_energy': Decimal('25.00'), 'cost_gas': Decimal('15.00'), 'is_custom': True},
        ]
    },
    {
        'po_number': 'PO-2024-003',
        'client_name': 'Gamma Solutions',
        'items': [
            {'sku': 'FLEX-4000', 'quantity': 120, 'price': Decimal('195.00'), 'cost_mp': Decimal('105.00'), 
             'cost_mo': Decimal('32.00'), 'cost_energy': Decimal('10.00'), 'cost_gas': Decimal('6.00'), 'is_custom': False},
            {'sku': 'FLEX-CUSTOM-B', 'quantity': 40, 'price': Decimal('580.00'), 'cost_mp': Decimal('310.00'), 
             'cost_mo': Decimal('95.00'), 'cost_energy': Decimal('22.00'), 'cost_gas': Decimal('13.00'), 'is_custom': True},
        ]
    },
    {
        'po_number': 'PO-2024-004',
        'client_name': 'Delta Corp',
        'items': [
            {'sku': 'FLEX-5000', 'quantity': 90, 'price': Decimal('325.00'), 'cost_mp': Decimal('175.00'), 
             'cost_mo': Decimal('52.00'), 'cost_energy': Decimal('15.00'), 'cost_gas': Decimal('10.00'), 'is_custom': False},
            {'sku': 'FLEX-6000', 'quantity': 60, 'price': Decimal('480.00'), 'cost_mp': Decimal('260.00'), 
             'cost_mo': Decimal('78.00'), 'cost_energy': Decimal('20.00'), 'cost_gas': Decimal('14.00'), 'is_custom': False},
        ]
    },
]


def get_or_create_tenant(db: Session) -> Tenant:
    """Obtém ou cria o tenant PromaFlex"""
    tenant = db.query(Tenant).filter(Tenant.cnpj == "12.345.678/0001-90").first()
    if not tenant:
        print("⚠️  Tenant PromaFlex não encontrado. Execute 'python backend/create_admin.py' primeiro!")
        sys.exit(1)
    return tenant


def get_admin_user(db: Session, tenant_id) -> User:
    """Obtém o usuário admin"""
    user = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.role == "admin"
    ).first()
    if not user:
        print("⚠️  Usuário admin não encontrado. Execute 'python backend/create_admin.py' primeiro!")
        sys.exit(1)
    return user


def seed_orders(db: Session):
    """Insere os pedidos demo no banco de dados"""
    
    print("\n" + "="*70)
    print("🚀 FlexFlow - Seed Showroom para Kickoff")
    print("="*70)
    
    # Obter tenant e usuário
    tenant = get_or_create_tenant(db)
    admin_user = get_admin_user(db, tenant.id)
    
    print(f"\n📦 Tenant: {tenant.name} (ID: {tenant.id})")
    print(f"👤 Usuário: {admin_user.name} (ID: {admin_user.id})")
    
    # Verificar se já existem pedidos
    existing_count = db.query(PurchaseOrder).filter(
        PurchaseOrder.tenant_id == tenant.id
    ).count()
    
    if existing_count > 0:
        print(f"\n⚠️  Já existem {existing_count} pedidos no banco de dados.")
        response = input("Deseja continuar e adicionar mais pedidos? (s/N): ")
        if response.lower() != 's':
            print("❌ Operação cancelada.")
            return
    
    print(f"\n📊 Inserindo {len(DEMO_ORDERS)} pedidos com total de {sum(len(order['items']) for order in DEMO_ORDERS)} itens...")
    
    created_pos = []
    total_items = 0
    custom_items = 0
    
    try:
        for order_data in DEMO_ORDERS:
            # Criar Purchase Order
            po = PurchaseOrder(
                tenant_id=tenant.id,
                po_number=order_data['po_number'],
                status_macro=PurchaseOrder.STATUS_DRAFT,  # Status inicial
                created_by=admin_user.id
            )
            db.add(po)
            db.flush()  # Flush para obter o ID
            
            print(f"\n  ✅ Pedido {order_data['po_number']} criado")
            print(f"     Cliente: {order_data['client_name']}")
            
            # Criar itens do pedido
            for item_data in order_data['items']:
                item = OrderItem(
                    po_id=po.id,
                    tenant_id=tenant.id,
                    sku=item_data['sku'],
                    quantity=item_data['quantity'],
                    price=item_data['price'],
                    status_item=OrderItem.STATUS_PENDING  # Status inicial
                )
                db.add(item)
                
                total_cost = (item_data['cost_mp'] + item_data['cost_mo'] + 
                             item_data['cost_energy'] + item_data['cost_gas'])
                margin = item_data['price'] - total_cost
                margin_pct = (margin / item_data['price'] * 100) if item_data['price'] > 0 else 0
                
                custom_flag = "🎨 PERSONALIZADO" if item_data['is_custom'] else ""
                print(f"     • {item_data['sku']}: {item_data['quantity']} un × R$ {item_data['price']:.2f} "
                      f"(Margem: {margin_pct:.1f}%) {custom_flag}")
                
                total_items += 1
                if item_data['is_custom']:
                    custom_items += 1
            
            created_pos.append(po)
        
        # Commit da transação
        db.commit()
        
        print("\n" + "="*70)
        print("✅ SEED CONCLUÍDO COM SUCESSO!")
        print("="*70)
        print(f"\n📈 ESTATÍSTICAS:")
        print(f"   • Pedidos criados: {len(created_pos)}")
        print(f"   • Total de itens: {total_items}")
        print(f"   • Itens personalizados: {custom_items}")
        print(f"   • Tenant: {tenant.name}")
        
        print(f"\n💡 PRÓXIMOS PASSOS:")
        print(f"   1. Acesse o sistema: http://localhost:3000")
        print(f"   2. Faça login com: admin@botcase.com.br / admin123")
        print(f"   3. Navegue até o Dashboard para ver os pedidos")
        print(f"   4. Use o Kanban para visualizar o workflow")
        print("="*70 + "\n")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Erro ao inserir pedidos: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Função principal"""
    print("\n🔍 Verificando conexão com o banco de dados...")
    
    try:
        # Testa a conexão
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        print("✅ Conexão com o banco de dados estabelecida!")
        db.close()
    except Exception as e:
        print(f"\n❌ Erro ao conectar ao banco de dados:")
        print(f"   {str(e)}")
        print("\n💡 Verifique se:")
        print("   1. O Cloud SQL Proxy está rodando")
        print("   2. As credenciais estão corretas")
        print("   3. O banco de dados existe")
        sys.exit(1)
    
    # Executar seed
    db = SessionLocal()
    try:
        seed_orders(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
