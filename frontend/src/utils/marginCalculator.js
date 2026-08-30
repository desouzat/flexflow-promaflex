/**
 * FlexFlow - Dynamic Margin Engine
 * Celso's Formula, Unit-Aware Cost Calculation Engine, and Payment Term Parsers
 */

/**
 * Robustly parses payment terms string into average days.
 * Examples:
 * - "30 dias" -> 30
 * - "30/60/90 dias" -> (30 + 60 + 90) / 3 = 60
 * - "À vista" / "A vista" -> 0
 * 
 * @param {string|null|undefined} terms - The payment term string
 * @returns {number} Average payment term in days
 */
export function parsePaymentTermsToDays(terms) {
    if (!terms) return 0;
    const termStr = String(terms).toLowerCase().trim();
    
    // Check for immediate/cash payment terms
    if (
        termStr.includes('à vista') || 
        termStr.includes('a vista') || 
        termStr.includes('imediato') || 
        termStr.includes('cash') || 
        termStr.includes('0 dias')
    ) {
        return 0;
    }
    
    // Find all numbers in the string
    const numbers = termStr.match(/\d+/g);
    if (!numbers || numbers.length === 0) return 0;
    
    const days = numbers.map(Number);
    // Return average of all installments (e.g. "30/60/90" -> 60)
    const averageDays = days.reduce((sum, val) => sum + val, 0) / days.length;
    return parseFloat(averageDays.toFixed(4));
}

/**
 * Unit-Aware Cost Calculation Engine
 * Calculates item total cost strictly respecting item unit of measurement (M2, KG, RL, UN).
 * 
 * Rules:
 * - KG: cost = qty_kg * (cost_m2 * yield_m2_per_kg)
 * - M2: cost = qty_m2 * cost_m2
 * - RL / UN: total_m2 = (width_m * length_m * qty), cost = total_m2 * cost_m2
 * - Fallback: cost = qty * cost_m2
 * 
 * @param {object} item - Item object
 * @param {object} [material] - Optional MaterialCost object
 * @returns {number} Total cost for the item
 */
export function calculateUnitAwareItemCost(item, material = null) {
    if (!item) return 0;

    const mat = material || item.material || item.material_cost || item.extra_metadata?.material || {};
    const costPerM2 = parseFloat(
        mat.custo_mp_kg ?? 
        item.custo_mp_kg ?? 
        item.cost_mp ?? 
        item.extra_metadata?.custo_mp_kg ?? 
        item.extra_metadata?.cost_mp ?? 
        0
    ) || 0;
    
    const yieldValue = parseFloat(
        mat.rendimento ?? 
        item.rendimento ?? 
        item.extra_metadata?.rendimento ?? 
        1
    ) || 1;

    const unit = (
        item.unidade_medida ||
        item.unit ||
        item.extra_metadata?.unidade_medida ||
        item.extra_metadata?.unit ||
        item.extra_metadata?.['Un. Med.'] ||
        item.extra_metadata?.['Unidade'] ||
        'M2'
    ).toString().toUpperCase().trim();

    const qty = parseFloat(
        item.quantity ?? 
        item.qty ?? 
        item.quantidade ?? 
        item.extra_metadata?.quantity ?? 
        item.extra_metadata?.quantidade ?? 
        0
    ) || 0;

    if (costPerM2 <= 0) {
        const fallbackCost = parseFloat(
            item.total_cost ?? 
            item.cost_mp ?? 
            item.extra_metadata?.total_cost ?? 
            item.extra_metadata?.cost_mp ?? 
            0
        ) || 0;
        if (fallbackCost > 0) return fallbackCost * qty;
        return 0;
    }

    if (unit === 'KG') {
        // For KG orders: cost = qty_kg * (cost_m2 * yield_m2_per_kg)
        const costPerKg = costPerM2 * yieldValue;
        return qty * costPerKg;
    } else if (unit === 'M2') {
        // For M2 orders: cost = qty_m2 * cost_m2
        return qty * costPerM2;
    } else if (unit === 'RL' || unit === 'UN') {
        // For Rolls/Units: calculate total m2 area = (width_mm / 1000) * length_m * qty
        const widthMm = parseFloat(
            item.width ?? 
            item.largura ?? 
            item.extra_metadata?.width ?? 
            item.extra_metadata?.largura ?? 
            item.extra_metadata?.['Largura (mm)'] ?? 
            0
        ) || 0;
        const lengthM = parseFloat(
            item.length ?? 
            item.comprimento ?? 
            item.extra_metadata?.length ?? 
            item.extra_metadata?.comprimento ?? 
            item.extra_metadata?.['Comprimento (m)'] ?? 
            0
        ) || 0;
        const widthM = widthMm / 1000.0;
        const totalAreaM2 = (widthM > 0 && lengthM > 0) ? (widthM * lengthM * qty) : qty;
        return totalAreaM2 * costPerM2;
    } else {
        // Fallback: cost = qty * cost_m2
        return qty * costPerM2;
    }
}

/**
 * Calculates Dynamic Contribution Margin (CM) using Celso's Formula.
 * All calculations are done using 4-decimal precision internally.
 * 
 * Formula: CM = (VP - Taxes - Commission - Freight) / Costs
 * 
 * @param {object} params
 * @param {number} params.gross - Gross value (price unit * quantity, or unit price)
 * @param {number} params.freight - Freight cost
 * @param {number} params.commissionRate - Commission rate percentage (e.g. 2.5 for 2.5%)
 * @param {number} params.costs - SKU unit cost or production costs (mp + mo + energy + gas)
 * @param {number} params.paymentDays - Payment term in days
 * @param {number} [params.taxRate=9.25] - Tax rate percentage (defaults to 9.25% PIS/COFINS; was 22.25)
 * @returns {object} Status, margin (percentage), and detailed internal breakdown
 */
export function calculateDynamicMargin({
    gross,
    freight = 0,
    commissionRate = 2.5,
    costs = 0,
    paymentDays = 0,
    taxRate,
    icmsRate = 0
}) {
    // Null Safety check: If cost is missing, undefined, or <= 0, return PENDENTE_PCP
    const parsedCosts = parseFloat(costs);
    if (isNaN(parsedCosts) || parsedCosts <= 0) {
        return {
            status: 'PENDENTE_PCP',
            margin: null,
            badgeColor: 'gray',
            formattedMargin: 'PENDENTE PCP',
            breakdown: null
        };
    }

    const parsedGross = parseFloat(gross) || 0;
    const parsedFreight = parseFloat(freight) || 0;
    const parsedCommissionRate = parseFloat(commissionRate) || 0;
    const rawIcmsRate = parseFloat(icmsRate) || 0;
    
    // Total dynamic tax rate = 9.25% PIS/COFINS + Item's specific ONET % ICMS
    const parsedTaxRate = taxRate !== undefined ? parseFloat(taxRate) : (9.25 + rawIcmsRate);

    // 1. VP (Present Value) = Gross / (1.025 ** (paymentDays / 30))
    const vpFactor = Math.pow(1.025, paymentDays / 30);
    const vp = parseFloat((parsedGross / vpFactor).toFixed(4));

    // 2. Taxes = VP * taxRate%
    const taxes = parseFloat((vp * (parsedTaxRate / 100)).toFixed(4));

    // 3. Commission = VP * commissionRate%
    const commission = parseFloat((vp * (parsedCommissionRate / 100)).toFixed(4));

    // 4. Contribution Margin / Net Revenue (VP - Taxes - Commission - Freight)
    const absoluteMargin = parseFloat((vp - taxes - commission - parsedFreight).toFixed(4));

    // 5. Net Profit (Lucro Líquido) = Net Revenue - Costs
    const netProfit = parseFloat((absoluteMargin - parsedCosts).toFixed(4));

    // 6. Net Profit Margin Percentage over Gross Revenue (Margem Líquida sobre Vendas)
    const revenueBase = parsedGross || vp || 1;
    const marginRatio = parseFloat((netProfit / revenueBase).toFixed(6));
    const marginPercentage = parseFloat((marginRatio * 100).toFixed(2));

    let badgeColor = 'green';
    if (marginPercentage < 10) {
        badgeColor = 'red';
    } else if (marginPercentage < 19) {
        badgeColor = 'orange';
    } else if (marginPercentage < 30) {
        badgeColor = 'yellow';
    }

    const formattedMargin = marginPercentage > 1000 ? '> 1000%' : `${marginPercentage.toFixed(2)}%`;

    return {
        status: 'OK',
        margin: marginPercentage, // internal precision
        badgeColor,
        formattedMargin,
        breakdown: {
            gross: parseFloat(parsedGross.toFixed(4)),
            vp: vp,
            vpDiscount: parseFloat((parsedGross - vp).toFixed(4)),
            icmsRate: rawIcmsRate,
            taxRate: parsedTaxRate,
            taxes: taxes,
            commission: commission,
            freight: parseFloat(parsedFreight.toFixed(4)),
            costs: parseFloat(parsedCosts.toFixed(4)),
            absoluteMargin: absoluteMargin,
            netProfit: netProfit
        }
    };
}

/**
 * Aggregates item-level dynamic margin metrics to calculate overall PO-level margins.
 * Done with 4-decimal internal precision.
 * 
 * @param {object} po - Purchase Order object
 * @returns {object} Status, aggregated margin (percentage), and detailed PO breakdown
 */
export function calculatePOMargins(po) {
    if (!po || !Array.isArray(po.items) || po.items.length === 0) {
        return {
            status: 'PENDENTE_PCP',
            margin: null,
            badgeColor: 'gray',
            formattedMargin: 'PENDENTE PCP',
            breakdown: null
        };
    }

    let totalGross = 0;
    let totalVP = 0;
    let totalTaxes = 0;
    let totalCommission = 0;
    let totalFreight = 0;
    let totalCosts = 0;
    let weightedIcmsSum = 0;
    let hasPendingCost = false;

    // Sum up items
    po.items.forEach(item => {
        const qty = parseFloat(item.quantity ?? item.qty ?? item.quantidade) || 0;
        if (qty <= 0) return;

        // Calculate item total cost using unit-aware calculation engine
        let itemTotalCost = calculateUnitAwareItemCost(item);

        if (itemTotalCost <= 0) {
            // Check legacy cost_mp fallback
            const legacyUnitCost = 
                parseFloat(item.total_cost) || 
                parseFloat(item.cost_mp) || 
                parseFloat(item.extra_metadata?.total_cost) || 
                parseFloat(item.extra_metadata?.cost_mp) || 
                0;
            if (legacyUnitCost > 0) {
                itemTotalCost = legacyUnitCost * qty;
            } else {
                hasPendingCost = true;
            }
        }

        const priceUnit = 
            parseFloat(item.unit_value) || 
            parseFloat(item.price_unit) || 
            parseFloat(item.price) || 
            0;

        const itemGross = priceUnit * qty;
        const paymentTermsStr = 
            item.payment_terms || 
            item.extra_metadata?.payment_terms || 
            item.extra_metadata?.['Cond.Pgto'] || 
            item.extra_metadata?.['Cond. Pgto'] || 
            item.extra_metadata?.['Cond.Pagto'] || 
            item.extra_metadata?.['Condição de Pagamento'] || 
            po.payment_terms || 
            po.extra_metadata?.payment_terms || 
            po.extra_metadata?.['Cond.Pgto'] || 
            po.extra_metadata?.['Cond. Pgto'] || 
            po.extra_metadata?.['Cond.Pagto'] || 
            po.extra_metadata?.['Condição de Pagamento'] || 
            po.partition_metadata?.payment_terms || 
            po.partition_metadata?.['Cond.Pgto'];

        const days = parsePaymentTermsToDays(paymentTermsStr);
        
        const vpFactor = Math.pow(1.025, days / 30);
        const itemVP = itemGross / vpFactor;

        // Dynamic ICMS rate from item metadata (default to 0% if missing)
        const rawIcmsRate = parseFloat(
            item.icms_rate ?? 
            item.icms_percent ?? 
            item.extra_metadata?.icms_rate ?? 
            item.extra_metadata?.icms_percent ?? 
            item.extra_metadata?.['% ICMS'] ?? 
            0
        ) || 0;

        // Total dynamic tax rate = 9.25% PIS/COFINS + Item's specific ONET % ICMS
        const itemTaxRate = 9.25 + rawIcmsRate;
        const itemTaxes = itemVP * (itemTaxRate / 100);

        // Try getting commission rate from item or PO
        const commissionRate = 
            parseFloat(item.manual_commission_rate) || 
            parseFloat(item.extra_metadata?.manual_commission_rate) || 
            parseFloat(po.commission_rate) || 
            2.5;
        
        const itemCommission = itemVP * (commissionRate / 100);
        const itemFreight = parseFloat(item.freight) || 0;

        totalGross += itemGross;
        totalVP += itemVP;
        totalTaxes += itemTaxes;
        totalCommission += itemCommission;
        totalFreight += itemFreight;
        totalCosts += itemTotalCost;
        weightedIcmsSum += (rawIcmsRate * itemGross);
    });

    // If costs are missing or zero for any item, mark PO as PCP pending
    if (hasPendingCost || totalCosts <= 0) {
        return {
            status: 'PENDENTE_PCP',
            margin: null,
            badgeColor: 'gray',
            formattedMargin: 'PENDENTE PCP',
            breakdown: null
        };
    }

    // Apply high-precision roundings internally
    totalGross = parseFloat(totalGross.toFixed(4));
    totalVP = parseFloat(totalVP.toFixed(4));
    totalTaxes = parseFloat(totalTaxes.toFixed(4));
    totalCommission = parseFloat(totalCommission.toFixed(4));
    
    // Add header values to totals
    const headerFreight = parseFloat(po.freight_cost) || parseFloat(po.extra_metadata?.freight_cost) || 0;
    const headerAdditionalCosts = parseFloat(po.additional_costs) || parseFloat(po.extra_metadata?.additional_costs) || 0;
    
    totalFreight += headerFreight;
    totalCosts += headerAdditionalCosts;

    totalFreight = parseFloat(totalFreight.toFixed(4));
    totalCosts = parseFloat(totalCosts.toFixed(4));

    const totalAbsoluteMargin = parseFloat((totalVP - totalTaxes - totalCommission - totalFreight).toFixed(4));
    const totalNetProfit = parseFloat((totalAbsoluteMargin - totalCosts).toFixed(4));

    const revenueBase = totalGross || totalVP || 1;
    const marginRatio = parseFloat((totalNetProfit / revenueBase).toFixed(6));
    const marginPercentage = parseFloat((marginRatio * 100).toFixed(2));

    let badgeColor = 'green';
    if (marginPercentage < 10) {
        badgeColor = 'red';
    } else if (marginPercentage < 19) {
        badgeColor = 'orange';
    } else if (marginPercentage < 30) {
        badgeColor = 'yellow';
    }

    const formattedMargin = marginPercentage > 1000 ? '> 1000%' : `${marginPercentage.toFixed(2)}%`;

    const averageIcmsRate = totalGross > 0 ? parseFloat((weightedIcmsSum / totalGross).toFixed(2)) : 0;

    return {
        status: 'OK',
        margin: marginPercentage,
        badgeColor,
        formattedMargin,
        breakdown: {
            gross: totalGross,
            vp: totalVP,
            vpDiscount: parseFloat((totalGross - totalVP).toFixed(4)),
            icmsRate: averageIcmsRate,
            taxRate: parseFloat((9.25 + averageIcmsRate).toFixed(2)),
            taxes: totalTaxes,
            commission: totalCommission,
            freight: totalFreight,
            costs: totalCosts,
            absoluteMargin: totalAbsoluteMargin,
            netProfit: totalNetProfit
        }
    };
}
