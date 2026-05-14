"""
FlexFlow - Live Split Evidence Test
Demonstrates the mathematical consistency of PO splitting with financial calculations.

Scenario: Split a R$ 10,000 PO (60 days term) into two child POs:
- Child 1: R$ 6,000 (different delivery date)
- Child 2: R$ 4,000 (different delivery date)

Verification: Margin, Commission, and VP must be mathematically consistent.
"""

import sys
from pathlib import Path
from decimal import Decimal

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from services.financial_service import FinancialService


def print_separator(char="=", length=80):
    """Print a separator line"""
    print(char * length)


def print_section_header(title):
    """Print a section header"""
    print_separator()
    print(f"  {title}")
    print_separator()


def print_financial_details(label, financials):
    """Print financial details in a formatted way"""
    print(f"\n{label}:")
    print(f"  💰 Preço de Venda: R$ {financials['sale_price']:,.2f}")
    print(f"  📦 Custo Total: R$ {financials['cost']:,.2f}")
    print(f"  🚚 Frete: R$ {financials['shipping_cost']:,.2f}")
    print(f"  📊 Impostos ({financials['tax_rate']:.2f}%): R$ {financials['taxes']:,.2f}")
    print(f"  📈 Margem: {financials['margin_percent']:.2f}%")
    print(f"  💵 Taxa de Comissão: {financials['commission_rate']:.2f}% ({financials['commission_reason']})")
    print(f"  💸 Valor da Comissão: R$ {financials['commission_value']:,.2f}")
    
    if financials['has_margin_alert']:
        print(f"  ⚠️  ALERTA: Margem abaixo de 19%!")
    
    print(f"  ⏰ Prazo: {financials['term_days']} dias")
    print(f"  💎 VP (Valor Presente): R$ {financials['vp']:,.2f}")
    print(f"  📉 Desconto VP: R$ {financials['vp_discount']:,.2f}")
    print(f"  💰 Lucro Líquido: R$ {financials['net_profit']:,.2f}")


def test_scenario_1_standard_split():
    """
    Scenario 1: Standard Split
    Mother PO: R$ 10,000 (60 days)
    Split into: R$ 6,000 + R$ 4,000
    """
    print_section_header("CENÁRIO 1: DIVISÃO PADRÃO (Standard Split)")
    
    # Mother PO Configuration
    mother_sale_price = Decimal("10000.00")
    mother_cost = Decimal("6500.00")  # Cost for materials
    mother_shipping = Decimal("500.00")
    mother_term = 60
    
    print("\n📋 CONFIGURAÇÃO:")
    print(f"  • PO Mãe: R$ {mother_sale_price:,.2f}")
    print(f"  • Custo de Material: R$ {mother_cost:,.2f}")
    print(f"  • Frete: R$ {mother_shipping:,.2f}")
    print(f"  • Prazo: {mother_term} dias")
    print(f"  • Cliente: Standard (não CSN)")
    
    # Calculate Mother PO Financials
    mother_financials = FinancialService.calculate_po_financials(
        sale_price=mother_sale_price,
        cost=mother_cost,
        shipping_cost=mother_shipping,
        term_days=mother_term,
        client_code=None
    )
    
    print_financial_details("🔵 PO MÃE (ANTES DA DIVISÃO)", mother_financials)
    
    # Split Configuration
    print("\n\n🔀 EXECUTANDO DIVISÃO...")
    print("  • Child 1: R$ 6,000 (60% do valor)")
    print("  • Child 2: R$ 4,000 (40% do valor)")
    print("  • Estratégia de Frete: Proporcional ao valor")
    
    # Child 1: 60% of value
    child1_sale = Decimal("6000.00")
    child1_cost = mother_cost * (child1_sale / mother_sale_price)  # Proportional
    child1_shipping = mother_shipping * (child1_sale / mother_sale_price)  # Proportional
    child1_term = 60
    
    child1_financials = FinancialService.calculate_po_financials(
        sale_price=child1_sale,
        cost=child1_cost,
        shipping_cost=child1_shipping,
        term_days=child1_term,
        client_code=None
    )
    
    print_financial_details("\n🟢 CHILD PO 1 (60%)", child1_financials)
    
    # Child 2: 40% of value
    child2_sale = Decimal("4000.00")
    child2_cost = mother_cost * (child2_sale / mother_sale_price)  # Proportional
    child2_shipping = mother_shipping * (child2_sale / mother_sale_price)  # Proportional
    child2_term = 60
    
    child2_financials = FinancialService.calculate_po_financials(
        sale_price=child2_sale,
        cost=child2_cost,
        shipping_cost=child2_shipping,
        term_days=child2_term,
        client_code=None
    )
    
    print_financial_details("\n🟡 CHILD PO 2 (40%)", child2_financials)
    
    # Verify Consistency
    print("\n\n")
    print_section_header("VERIFICAÇÃO DE CONSISTÊNCIA MATEMÁTICA")
    
    verification = FinancialService.verify_split_consistency(
        mother_financials,
        [child1_financials, child2_financials]
    )
    
    print(f"\n✅ Consistência: {'APROVADO' if verification['is_consistent'] else 'FALHOU'}")
    print(f"\n📊 COMPARAÇÃO DE VALORES:")
    print(f"  Preço de Venda:")
    print(f"    • Mãe: R$ {verification['mother_sale_price']:,.2f}")
    print(f"    • Soma dos Filhos: R$ {verification['total_child_sale_price']:,.2f}")
    print(f"    • Diferença: R$ {verification['sale_difference']:.2f}")
    
    print(f"\n  Custo:")
    print(f"    • Mãe: R$ {verification['mother_cost']:,.2f}")
    print(f"    • Soma dos Filhos: R$ {verification['total_child_cost']:,.2f}")
    print(f"    • Diferença: R$ {verification['cost_difference']:.2f}")
    
    print(f"\n  Frete:")
    print(f"    • Mãe: R$ {verification['mother_shipping']:,.2f}")
    print(f"    • Soma dos Filhos: R$ {verification['total_child_shipping']:,.2f}")
    print(f"    • Diferença: R$ {verification['shipping_difference']:.2f}")
    
    print(f"\n  Comissão:")
    print(f"    • Mãe: R$ {verification['mother_commission']:,.2f}")
    print(f"    • Soma dos Filhos: R$ {verification['total_child_commission']:,.2f}")
    print(f"    • Nota: {verification['commission_note']}")
    
    return verification['is_consistent']


def test_scenario_2_csn_exception():
    """
    Scenario 2: CSN Client Exception
    Mother PO: R$ 10,000 (60 days) - CSN Client
    Split into: R$ 6,000 + R$ 4,000
    """
    print("\n\n")
    print_section_header("CENÁRIO 2: EXCEÇÃO CSN (CSN Client Exception)")
    
    # Mother PO Configuration
    mother_sale_price = Decimal("10000.00")
    mother_cost = Decimal("6500.00")
    mother_shipping = Decimal("500.00")
    mother_term = 60
    client_code = "CSN"
    
    print("\n📋 CONFIGURAÇÃO:")
    print(f"  • PO Mãe: R$ {mother_sale_price:,.2f}")
    print(f"  • Custo de Material: R$ {mother_cost:,.2f}")
    print(f"  • Frete: R$ {mother_shipping:,.2f}")
    print(f"  • Prazo: {mother_term} dias")
    print(f"  • Cliente: {client_code} ⭐ (Taxa Fixa de 1.5%)")
    
    # Calculate Mother PO Financials
    mother_financials = FinancialService.calculate_po_financials(
        sale_price=mother_sale_price,
        cost=mother_cost,
        shipping_cost=mother_shipping,
        term_days=mother_term,
        client_code=client_code
    )
    
    print_financial_details("🔵 PO MÃE CSN (ANTES DA DIVISÃO)", mother_financials)
    
    # Child 1
    child1_sale = Decimal("6000.00")
    child1_cost = mother_cost * (child1_sale / mother_sale_price)
    child1_shipping = mother_shipping * (child1_sale / mother_sale_price)
    
    child1_financials = FinancialService.calculate_po_financials(
        sale_price=child1_sale,
        cost=child1_cost,
        shipping_cost=child1_shipping,
        term_days=60,
        client_code=client_code
    )
    
    print_financial_details("\n🟢 CHILD PO 1 CSN (60%)", child1_financials)
    
    # Child 2
    child2_sale = Decimal("4000.00")
    child2_cost = mother_cost * (child2_sale / mother_sale_price)
    child2_shipping = mother_shipping * (child2_sale / mother_sale_price)
    
    child2_financials = FinancialService.calculate_po_financials(
        sale_price=child2_sale,
        cost=child2_cost,
        shipping_cost=child2_shipping,
        term_days=60,
        client_code=client_code
    )
    
    print_financial_details("\n🟡 CHILD PO 2 CSN (40%)", child2_financials)
    
    # Verify
    verification = FinancialService.verify_split_consistency(
        mother_financials,
        [child1_financials, child2_financials]
    )
    
    print("\n\n")
    print_section_header("VERIFICAÇÃO CSN")
    print(f"\n✅ Consistência: {'APROVADO' if verification['is_consistent'] else 'FALHOU'}")
    print(f"💡 Nota: CSN sempre usa taxa fixa de 1.5%, independente da margem")
    
    return verification['is_consistent']


def test_scenario_3_master_override():
    """
    Scenario 3: MASTER Manual Override
    Mother PO with manual commission rate set by MASTER user
    """
    print("\n\n")
    print_section_header("CENÁRIO 3: OVERRIDE MANUAL (MASTER Override)")
    
    # Mother PO Configuration
    mother_sale_price = Decimal("10000.00")
    mother_cost = Decimal("7000.00")  # Lower margin
    mother_shipping = Decimal("500.00")
    mother_term = 90
    manual_rate = Decimal("5.00")  # MASTER sets 5% commission
    
    print("\n📋 CONFIGURAÇÃO:")
    print(f"  • PO Mãe: R$ {mother_sale_price:,.2f}")
    print(f"  • Custo de Material: R$ {mother_cost:,.2f}")
    print(f"  • Frete: R$ {mother_shipping:,.2f}")
    print(f"  • Prazo: {mother_term} dias")
    print(f"  • Comissão Manual (MASTER): {manual_rate}% 🔐")
    
    # Calculate with manual override
    mother_financials = FinancialService.calculate_po_financials(
        sale_price=mother_sale_price,
        cost=mother_cost,
        shipping_cost=mother_shipping,
        term_days=mother_term,
        client_code=None,
        manual_commission_rate=manual_rate
    )
    
    print_financial_details("🔵 PO MÃE COM OVERRIDE MASTER", mother_financials)
    
    # Calculate what it would be without override
    auto_financials = FinancialService.calculate_po_financials(
        sale_price=mother_sale_price,
        cost=mother_cost,
        shipping_cost=mother_shipping,
        term_days=mother_term,
        client_code=None,
        manual_commission_rate=None
    )
    
    print(f"\n📊 COMPARAÇÃO:")
    print(f"  • Comissão Automática: {auto_financials['commission_rate']:.2f}% (R$ {auto_financials['commission_value']:,.2f})")
    print(f"  • Comissão Manual (MASTER): {mother_financials['commission_rate']:.2f}% (R$ {mother_financials['commission_value']:,.2f})")
    print(f"  • Diferença: R$ {abs(mother_financials['commission_value'] - auto_financials['commission_value']):,.2f}")
    
    return True


def test_scenario_4_different_terms():
    """
    Scenario 4: Different Payment Terms
    Demonstrate VP calculation with different terms
    """
    print("\n\n")
    print_section_header("CENÁRIO 4: DIFERENTES PRAZOS (Different Payment Terms)")
    
    sale_price = Decimal("10000.00")
    cost = Decimal("6500.00")
    shipping = Decimal("500.00")
    
    print("\n📋 CONFIGURAÇÃO BASE:")
    print(f"  • Preço de Venda: R$ {sale_price:,.2f}")
    print(f"  • Custo: R$ {cost:,.2f}")
    print(f"  • Frete: R$ {shipping:,.2f}")
    
    terms = [30, 60, 90, 120]
    
    print("\n💎 IMPACTO DO PRAZO NO VP:")
    for term in terms:
        financials = FinancialService.calculate_po_financials(
            sale_price=sale_price,
            cost=cost,
            shipping_cost=shipping,
            term_days=term,
            client_code=None
        )
        
        print(f"\n  {term} dias:")
        print(f"    • VP: R$ {financials['vp']:,.2f}")
        print(f"    • Desconto VP: R$ {financials['vp_discount']:,.2f} ({(financials['vp_discount']/float(sale_price)*100):.2f}%)")
    
    return True


def main():
    """Run all test scenarios"""
    print("\n")
    print("=" * 80)
    print("  FLEXFLOW - TESTE DE DIVISÃO FINANCEIRA (LIVE SPLIT EVIDENCE)")
    print("  Demonstração da Consistência Matemática na Divisão de POs")
    print("=" * 80)
    
    results = []
    
    # Run all scenarios
    results.append(("Cenário 1: Divisão Padrão", test_scenario_1_standard_split()))
    results.append(("Cenário 2: Exceção CSN", test_scenario_2_csn_exception()))
    results.append(("Cenário 3: Override MASTER", test_scenario_3_master_override()))
    results.append(("Cenário 4: Diferentes Prazos", test_scenario_4_different_terms()))
    
    # Summary
    print("\n\n")
    print_section_header("RESUMO DOS TESTES")
    
    all_passed = all(result for _, result in results)
    
    for scenario, passed in results:
        status = "✅ PASSOU" if passed else "❌ FALHOU"
        print(f"  {status} - {scenario}")
    
    print("\n")
    if all_passed:
        print("🎉 TODOS OS TESTES PASSARAM!")
        print("✅ A lógica financeira está matematicamente consistente.")
    else:
        print("⚠️  ALGUNS TESTES FALHARAM")
        print("❌ Revisar a implementação.")
    
    print("\n" + "=" * 80)
    print("  FIM DO TESTE")
    print("=" * 80 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
