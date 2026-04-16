"""
FlexFlow - Script de Seed Completo para Workflow
Popula o board com 15 pedidos distribuídos em TODAS as colunas do Kanban
Inclui flags estratégicas (is_export, is_replacement) e impedimentos de produção
Popula material_costs com 10 itens
"""

import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal
import random

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Adiciona o diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import Tenant, User, PurchaseOrder, OrderItem, MaterialCost, ProductionImpediment


# Dados de materiais para custos
MATERIAL_COSTS_DATA = [
    {"sku": "PP-1000", "nome": "Polipropileno Natural", "custo_mp_kg": Decimal("8.50"), "rendimento": Decimal("0.92"), "indice_impostos": Decimal("22.25")},
    {"sku": "PP-2000", "nome": "Polipropileno Preto", "custo_mp_kg": Decimal("9.20"), "rendimento": Decimal("0.90"), "indice_impostos": Decimal("22.25")},
    {"sku": "PE-1000", "nome": "Polietileno HD Natural", "custo_mp_kg": Decimal("7.80"), "rendimento": Decimal("0.94"), "indice_impostos": Decimal("22.25")},
    {"sku": "PE-2000", "nome": "Polietileno LD Transparente", "custo_mp_kg": Decimal("8.90"), "rendimento": Decimal("0.91"), "indice_impostos": Decimal("22.25")},
    {"sku": "ABS-1000", "nome": "ABS Natural", "custo_mp_kg": Decimal("12.50"), "rendimento": Decimal("0.88"), "indice_impostos": Decimal("22.25")},
    {"sku": "ABS-2000", "nome": "ABS Preto", "custo_mp_kg": Decimal("13.20"), "rendimento": Decimal("0.87"), "indice_impostos": Decimal("22.25")},
    {"sku": "PET-1000", "nome": "PET Cristal", "custo_mp_kg": Decimal("10.50"), "rendimento": Decimal("0.93"), "indice_impostos": Decimal("22.25")},
    {"sku": "PVC-1000", "nome": "PVC Rígido", "custo_mp_kg": Decimal("6.80"), "rendimento": Decimal("0.89"), "indice_impostos": Decimal("22.25")},
    {"sku": "PS-1000", "nome": "Poliestireno Cristal", "custo_mp_kg": Decimal("9.50"), "rendimento": Decimal("0.90"), "indice_impostos": Decimal("22.25")},
    {"sku": "PC-1000", "nome": "Policarbonato Transparente", "custo_mp_kg": Decimal("18.50"), "rendimento": Decimal("0.85"), "indice_impostos": Decimal("22.25")},
]


# Dados dos pedidos - 15 pedidos distribuídos em 5 colunas
DEMO_ORDERS = [
    # PENDENTE (3 pedidos)
    {
        'po_number': 'PO-2024-001',
        'client_name': 'Acme Corp',
        'status_macro': 'DRAFT',
        'column': 'Pendente',
        'items': [
            {
                'sku': 'FLEX-1000', 'quantity': 100, 'price': Decimal('150.00'),
                'metadata': {'is_export': False, 'is_first_order': True, 'is_replacement': False, 'is_urgent': False}
            },
            {
                'sku': 'FLEX-2000', 'quantity': 50, 'price': Decimal('280.00'),
                'metadata': {'is_export': False, 'is_first_order': False, 'is_replacement': False, 'is_urgent': False}
            },
        ]
    },
    {
        'po_number': 'PO-2024-002',
        'client_name': 'Beta Industries',
        'status_macro': 'DRAFT',
        'column': 'Pendente',
        'items': [
            {
                'sku': 'FLEX-3000', 'quantity': 75, 'price': Decimal('420.00'),
                'metadata': {'is_export': True, 'is_first_order': False, 'is_replacement': False, 'is_urgent': True}
            },
        ]
    },
    {
        'po_number': 'PO-2024-003',
        'client_name': 'Gamma Solutions',
        'status_macro': 'DRAFT',
        'column': 'Pendente',
        'items': [
            {
                'sku': 'FLEX-4000', 'quantity': 120, 'price': Decimal('195.00'),
                'metadata': {'is_export': False, 'is_first_order': False, 'is_replacement': True, 'is_urgent': False}
            },
        ]
    },
    
    # PCP (3 pedidos)
    {
        'po_number': 'PO-2024-004',
        'client_name': 'Delta Corp',
        'status_macro': 'APPROVED',
        'column': 'PCP',
        'items': [
            {
                'sku': 'FLEX-5000', 'quantity': 90, 'price': Decimal('325.00'),
                'metadata': {'is_export': False, 'is_first_order': False, 'is_replacement': False, 'is_urgent': False}
            },
            {
                'sku': 'FLEX-6000', 'quantity': 60, 'price': Decimal('480.00'),
                'metadata': {'is_export': True, 'is_first_order': False, 'is_replacement': False, 'is_urgent': False}
            },
        ]
    },
    {
        'po_number': 'PO-2024-005',
        'client_name': 'Epsilon Ltd',
        'status_macro': 'APPROVED',
        'column': 'PCP',
        'items': [
            {
                'sku': 'FLEX-7000', 'quantity': 200, 'price': Decimal('125.00'),
                'metadata': {'is_export': False, 'is_first_order': True, 'is_replacement': False, 'is_urgent': True}
            },
        ]
    },
    {
        'po_number': 'PO-2024-006',
        'client_name': 'Zeta Manufacturing',
        'status_macro': 'APPROVED',
        'column': 'PCP',
        'items': [
            {
                'sku': 'FLEX-8000', 'quantity': 150, 'price': Decimal('220.00'),
                'metadata': {'is_export': False, 'is_first_order': False, 'is_replacement': True, 'is_urgent': False}
            },
        ]
    },
    
    # PRODUÇÃO (4 pedidos - alguns com impedimentos)
    {
        'po_number': 'PO-2024-007',
        'client_name': 'Eta Enterprises',
        'status_macro': 'IN_PRODUCTION',
        'column': 'Produção',
        'items': [
            {
                'sku': 'FLEX-9000', 'quantity': 80, 'price': Decimal('380.00'),
                'metadata': {
                    'is_export': True, 'is_first_order': False, 'is_replacement': False, 'is_urgent': True,
                    'production_impediment': ProductionImpediment.FALTA_MATERIA_PRIMA.value,
                    'impediment_notes': 'Aguardando chegada de PP-2000'
                }
            },
        ]
    },
    {
        'po_number': 'PO-2024-008',
        'client_name': 'Theta Systems',
        'status_macro': 'IN_PRODUCTION',
        'column': 'Produção',
        'items': [
            {
                'sku': 'FLEX-10000', 'quantity': 110, 'price': Decimal('295.00'),
                'metadata': {'is_export': False, 'is_first_order': False, 'is_replacement': False, 'is_urgent': False}
            },
        ]
    },
    {
        'po_number': 'PO-2024-009',
        'client_name': 'Iota Industries',
        'status_macro': 'IN_PRODUCTION',
        'column': 'Produção',
        'items': [
            {
                'sku': 'FLEX-11000', 'quantity': 95, 'price': Decimal('410.00'),
                'metadata': {
                    'is_export': False, 'is_first_order': False, 'is_replacement': True, 'is_urgent': True,
                    'production_impediment': ProductionImpediment.EQUIPAMENTO_QUEBRADO.value,
                    'impediment_notes': 'Injetora 3 em manutenção - previsão 2 dias'
                }
            },
        ]
    },
    {
        'po_number': 'PO-2024-010',
        'client_name': 'Kappa Global',
        'status_macro': 'IN_PRODUCTION',
        'column': 'Produção',
        'items': [
            {
                'sku': 'FLEX-12000', 'quantity': 130, 'price': Decimal('175.00'),
                'metadata': {'is_export': True, 'is_first_order': True, 'is_replacement': False, 'is_urgent': False}
            },
        ]
    },
    
    # EXPEDIÇÃO (3 pedidos)
    {
        'po_number': 'PO-2024-011',
        'client_name': 'Lambda Logistics',
        'status_macro': 'READY_TO_SHIP',
        'column': 'Expedição',
        'items': [
            {
                'sku': 'FLEX-13000', 'quantity': 85, 'price': Decimal('340.00'),
                'metadata': {'is_export': False, 'is_first_order': False, 'is_replacement': False, 'is_urgent': False}
            },
        ]
    },
    {
        'po_number': 'PO-2024-012',
        'client_name': 'Mu Trading',
        'status_macro': 'READY_TO_SHIP',
        'column': 'Expedição',
        'items': [
            {
                'sku': 'FLEX-14000', 'quantity': 70, 'price': Decimal('520.00'),
                'metadata': {'is_export': True, 'is_first_order': False, 'is_replacement': False, 'is_urgent': True}
            },
        ]
    },
    {
        'po_number': 'PO-2024-013',
        'client_name': 'Nu Exports',
        'status_macro': 'READY_TO_SHIP',
        'column': 'Expedição',
        'items': [
            {
                'sku': 'FLEX-15000', 'quantity': 105, 'price': Decimal('265.00'),
                'metadata': {'is_export': False, 'is_first_order': False, 'is_replacement': True, 'is_urgent': False}
            },
        ]
    },
    
    # CONCLUÍDO (2 pedidos)
    {
        'po_number': 'PO-2024-014',
        'client_name': 'Xi Corporation',
        'status_macro': 'COMPLETED',
        'column': 'Concluído',
        'items': [
            {
                'sku': 'FLEX-16000', 'quantity': 140, 'price': Decimal('185.00'),
                'metadata': {'is_export': False, 'is_first_order': False, 'is_replacement': False, 'is_urgent': False}
            },
        ]
    },
    {
        'po_number': 'PO-2024-015',
        'client_name': 'Omicron Partners',
        'status_macro': 'COMPLETED',
        'column': 'Concluído',
        'items': [
            {
                'sku': 'FLEX-17000', 'quantity': 65, 'price': Decimal('450.00'),
                'metadata': {'is_export': True, 'is_first_order': True, 'is_replacement': False, 'is_urgent': False}
            },
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
        User.tenant_id == tenant_id
    ).first()
    if not user:
        print("⚠️  Nenhum usuário encontrado. Execute 'python backend/create_admin.py' primeiro!")
        sys.exit(1)
    return user


def seed_material_costs(db: Session, tenant_id):
    """Popula a tabela de custos de materiais"""
    print("\n📦 Populando custos de materiais...")
    
    # Verificar se já existem materiais
    existing_count = db.query(MaterialCost).filter(
        MaterialCost.tenant_id == tenant_id
    ).count()
    
    if existing_count > 0:
        print(f"   ⚠️  Já existem {existing_count} materiais cadastrados.")
        response = input("   Deseja limpar e recriar? (s/N): ")
        if response.lower() == 's':
            db.query(MaterialCost).filter(MaterialCost.tenant_id == tenant_id).delete()
            db.commit()
            print("   ✅ Materiais anteriores removidos.")
    
    created_count = 0
    for material_data in MATERIAL_COSTS_DATA:
        material = MaterialCost(
            tenant_id=tenant_id,
            **material_data
        )
        db.add(material)
        created_count += 1
        print(f"   ✅ {material_data['sku']}: {material_data['nome']} - R$ {material_data['custo_mp_kg']}/kg")
    
    db.commit()
    print(f"\n   📊 Total de materiais criados: {created_count}")


def seed_orders(db: Session):
    """Insere os pedidos demo no banco de dados"""
    
    print("\n" + "="*70)
    print("🚀 FlexFlow - Seed Completo de Workflow")
    print("="*70)
    
    # Obter tenant e usuário
    tenant = get_or_create_tenant(db)
    admin_user = get_admin_user(db, tenant.id)
    
    print(f"\n📦 Tenant: {tenant.name} (ID: {tenant.id})")
    print(f"👤 Usuário: {admin_user.name} (ID: {admin_user.id})")
    
    # Seed material costs
    seed_material_costs(db, tenant.id)
    
    # Verificar se já existem pedidos
    existing_count = db.query(PurchaseOrder).filter(
        PurchaseOrder.tenant_id == tenant.id
    ).count()
    
    if existing_count > 0:
        print(f"\n⚠️  Já existem {existing_count} pedidos no banco de dados.")
        response = input("Deseja limpar e recriar todos os pedidos? (s/N): ")
        if response.lower() == 's':
            # Deletar todos os pedidos (cascade vai deletar os itens)
            db.query(PurchaseOrder).filter(PurchaseOrder.tenant_id == tenant.id).delete()
            db.commit()
            print("✅ Pedidos anteriores removidos.")
        else:
            print("❌ Operação cancelada.")
            return
    
    print(f"\n📊 Inserindo {len(DEMO_ORDERS)} pedidos distribuídos em 5 colunas...")
    
    created_pos = []
    total_items = 0
    column_stats = {}
    
    try:
        for order_data in DEMO_ORDERS:
            # Criar Purchase Order
            po = PurchaseOrder(
                tenant_id=tenant.id,
                po_number=order_data['po_number'],
                status_macro=order_data['status_macro'],
                created_by=admin_user.id
            )
            db.add(po)
            db.flush()  # Flush para obter o ID
            
            column = order_data['column']
            column_stats[column] = column_stats.get(column, 0) + 1
            
            print(f"\n  ✅ Pedido {order_data['po_number']} criado [{column}]")
            print(f"     Cliente: {order_data['client_name']}")
            print(f"     Status: {order_data['status_macro']}")
            
            # Criar itens do pedido
            for item_data in order_data['items']:
                item = OrderItem(
                    po_id=po.id,
                    tenant_id=tenant.id,
                    sku=item_data['sku'],
                    quantity=item_data['quantity'],
                    price=item_data['price'],
                    status_item=OrderItem.STATUS_PENDING,
                    extra_metadata=item_data.get('metadata', {})
                )
                db.add(item)
                
                # Mostrar flags especiais
                metadata = item_data.get('metadata', {})
                flags = []
                if metadata.get('is_export'):
                    flags.append('🌍 EXPORTAÇÃO')
                if metadata.get('is_first_order'):
                    flags.append('⭐ PRIMEIRO PEDIDO')
                if metadata.get('is_replacement'):
                    flags.append('🔄 REPOSIÇÃO')
                if metadata.get('is_urgent'):
                    flags.append('⚡ URGENTE')
                if metadata.get('production_impediment'):
                    flags.append(f'⚠️ IMPEDIMENTO: {metadata["production_impediment"]}')
                
                flags_str = ' | '.join(flags) if flags else ''
                print(f"     • {item_data['sku']}: {item_data['quantity']} un × R$ {item_data['price']:.2f} {flags_str}")
                
                total_items += 1
            
            created_pos.append(po)
        
        # Commit da transação
        db.commit()
        
        print("\n" + "="*70)
        print("✅ SEED CONCLUÍDO COM SUCESSO!")
        print("="*70)
        print(f"\n📈 ESTATÍSTICAS:")
        print(f"   • Pedidos criados: {len(created_pos)}")
        print(f"   • Total de itens: {total_items}")
        print(f"   • Materiais cadastrados: {len(MATERIAL_COSTS_DATA)}")
        print(f"\n📊 DISTRIBUIÇÃO POR COLUNA:")
        for column, count in sorted(column_stats.items()):
            print(f"   • {column}: {count} pedidos")
        
        print(f"\n💡 PRÓXIMOS PASSOS:")
        print(f"   1. Acesse o sistema: http://localhost:5173")
        print(f"   2. Faça login com: admin@botcase.com.br / admin123")
        print(f"   3. Navegue até o Kanban para ver os 15 pedidos distribuídos")
        print(f"   4. Clique nos cards para ver detalhes e metadata")
        print(f"   5. Acesse 'Gerenciar Custos' para ver os materiais cadastrados")
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
