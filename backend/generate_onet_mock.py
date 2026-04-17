"""
FlexFlow - Gerador de Arquivo ONET Mock para Testes
Gera um arquivo Excel profissional com dados realistas para testar a Mesa de Conferência (Staging Area)
"""

import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal
import sys
import io

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def generate_onet_mock():
    """
    Gera arquivo Excel mock com as 14 colunas ONET definidas para Ewaldo.
    
    Inclui:
    - 2 itens com SKUs existentes em material_costs (PP-1000, ABS-2000)
    - 1 item com SKU novo (para trigger warning amarelo)
    - 2 itens que requerem toggle 'Personalizado'
    """
    
    # Data base para cálculos
    today = datetime.now()
    
    # Dados realistas para 5 linhas
    data = [
        {
            'Pedido': 'ONET-2024-1001',
            'Cliente': 'Indústria Automotiva XYZ Ltda',
            'SKU': 'PP-1000',  # ✅ EXISTE em material_costs
            'Descrição': 'Tampa Reservatório Polipropileno Natural',
            'Qtd': 500,
            'Unidade': 'UN',
            'Largura': 120.5,
            'Comprimento': 85.3,
            'Lead Time': 15,
            'Data Entrega': (today + timedelta(days=20)).strftime('%d/%m/%Y'),
            'Data Faturamento': (today + timedelta(days=18)).strftime('%d/%m/%Y'),
            '% ICMS': 18.0,
            'Frete': 450.00,
            'Seguro': 125.50
        },
        {
            'Pedido': 'ONET-2024-1002',
            'Cliente': 'Embalagens Premium S.A.',
            'SKU': 'ABS-2000',  # ✅ EXISTE em material_costs
            'Descrição': 'Caixa Organizadora ABS Preto com Tampa',
            'Qtd': 1000,
            'Unidade': 'UN',
            'Largura': 250.0,
            'Comprimento': 180.0,
            'Lead Time': 20,
            'Data Entrega': (today + timedelta(days=25)).strftime('%d/%m/%Y'),
            'Data Faturamento': (today + timedelta(days=23)).strftime('%d/%m/%Y'),
            '% ICMS': 12.0,
            'Frete': 680.00,
            'Seguro': 210.00
        },
        {
            'Pedido': 'ONET-2024-1003',
            'Cliente': 'Eletrônicos Delta Corp',
            'SKU': 'PAB-035',  # ⚠️ SKU NOVO - vai trigger warning amarelo
            'Descrição': 'Painel Frontal Customizado com Logo Gravado',  # 🔧 PERSONALIZADO
            'Qtd': 250,
            'Unidade': 'UN',
            'Largura': 300.0,
            'Comprimento': 200.0,
            'Lead Time': 30,
            'Data Entrega': (today + timedelta(days=35)).strftime('%d/%m/%Y'),
            'Data Faturamento': (today + timedelta(days=33)).strftime('%d/%m/%Y'),
            '% ICMS': 18.0,
            'Frete': 890.00,
            'Seguro': 340.00
        },
        {
            'Pedido': 'ONET-2024-1004',
            'Cliente': 'Móveis Modernos Ltda',
            'SKU': 'PE-1000',  # ✅ EXISTE em material_costs
            'Descrição': 'Gaveta Modular PE HD Natural com Divisórias Personalizadas',  # 🔧 PERSONALIZADO
            'Qtd': 750,
            'Unidade': 'UN',
            'Largura': 400.0,
            'Comprimento': 350.0,
            'Lead Time': 25,
            'Data Entrega': (today + timedelta(days=30)).strftime('%d/%m/%Y'),
            'Data Faturamento': (today + timedelta(days=28)).strftime('%d/%m/%Y'),
            '% ICMS': 12.0,
            'Frete': 1200.00,
            'Seguro': 450.00
        },
        {
            'Pedido': 'ONET-2024-1005',
            'Cliente': 'Farmacêutica BioHealth',
            'SKU': 'PET-1000',  # ✅ EXISTE em material_costs
            'Descrição': 'Frasco PET Cristal 500ml',
            'Qtd': 2000,
            'Unidade': 'UN',
            'Largura': 75.0,
            'Comprimento': 180.0,
            'Lead Time': 12,
            'Data Entrega': (today + timedelta(days=15)).strftime('%d/%m/%Y'),
            'Data Faturamento': (today + timedelta(days=14)).strftime('%d/%m/%Y'),
            '% ICMS': 18.0,
            'Frete': 320.00,
            'Seguro': 95.00
        }
    ]
    
    # Criar DataFrame
    df = pd.DataFrame(data)
    
    # Definir ordem exata das colunas conforme especificação Ewaldo
    columns_order = [
        'Pedido', 'Cliente', 'SKU', 'Descrição', 'Qtd', 'Unidade',
        'Largura', 'Comprimento', 'Lead Time', 'Data Entrega',
        'Data Faturamento', '% ICMS', 'Frete', 'Seguro'
    ]
    
    df = df[columns_order]
    
    # Gerar arquivo Excel com formatação profissional
    output_file = 'onet_test_data.xlsx'
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Pedidos ONET', index=False)
        
        # Obter worksheet para formatação
        worksheet = writer.sheets['Pedidos ONET']
        
        # Ajustar largura das colunas
        column_widths = {
            'A': 18,  # Pedido
            'B': 35,  # Cliente
            'C': 12,  # SKU
            'D': 50,  # Descrição
            'E': 8,   # Qtd
            'F': 10,  # Unidade
            'G': 12,  # Largura
            'H': 14,  # Comprimento
            'I': 12,  # Lead Time
            'J': 15,  # Data Entrega
            'K': 18,  # Data Faturamento
            'L': 10,  # % ICMS
            'M': 12,  # Frete
            'N': 12   # Seguro
        }
        
        for col, width in column_widths.items():
            worksheet.column_dimensions[col].width = width
        
        # Formatar cabeçalho (negrito)
        from openpyxl.styles import Font, PatternFill, Alignment
        
        header_font = Font(bold=True, size=11)
        header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center')
        
        for cell in worksheet[1]:
            cell.font = Font(bold=True, size=11, color='FFFFFF')
            cell.fill = header_fill
            cell.alignment = header_alignment
        
        # Alinhar dados
        for row in worksheet.iter_rows(min_row=2, max_row=len(df)+1):
            for idx, cell in enumerate(row):
                if idx in [4, 6, 7, 8, 11, 12, 13]:  # Colunas numéricas
                    cell.alignment = Alignment(horizontal='right')
                elif idx in [9, 10]:  # Datas
                    cell.alignment = Alignment(horizontal='center')
                else:
                    cell.alignment = Alignment(horizontal='left')
    
    print("=" * 80)
    print("[OK] Arquivo ONET Mock Gerado com Sucesso!")
    print("=" * 80)
    print(f"\nArquivo: {output_file}")
    print(f"Total de linhas: {len(df)}")
    print("\nResumo dos dados:")
    print(f"   - 2 itens com SKUs EXISTENTES (PP-1000, ABS-2000)")
    print(f"   - 1 item com SKU NOVO (PAB-035) - vai trigger WARNING amarelo")
    print(f"   - 2 itens PERSONALIZADOS (PAB-035, PE-1000)")
    print("\nCasos de teste incluidos:")
    print("   [x] SKUs existentes em material_costs")
    print("   [x] SKU novo para testar warning de custo nao encontrado")
    print("   [x] Itens que requerem toggle 'Personalizado'")
    print("   [x] Diferentes clientes e valores de ICMS")
    print("   [x] Variacao de quantidades e dimensoes")
    print("\n" + "=" * 80)
    print("\nProximo passo:")
    print("   Importe este arquivo na Mesa de Conferencia (Staging Area)")
    print("   para testar a validacao e preview dos dados ONET.")
    print("=" * 80)

if __name__ == "__main__":
    generate_onet_mock()
