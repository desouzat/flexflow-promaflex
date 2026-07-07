/**
 * FlexFlow - Dynamic Margin Engine
 * Celso's Formula and Payment Term Parsers
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
    commissionRate = 0,
    costs = 0,
    paymentDays = 0,
    taxRate = 9.25  // FF-HARDENING-015: PIS/COFINS unified rate (was 22.25)
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
    const parsedTaxRate = parseFloat(taxRate) || 9.25;  // FF-HARDENING-015: PIS/COFINS fallback

    // 1. VP (Present Value) = Gross / (1.025 ** (paymentDays / 30))
    const vpFactor = Math.pow(1.025, paymentDays / 30);
    const vp = parseFloat((parsedGross / vpFactor).toFixed(4));

    // 2. Taxes = VP * taxRate%
    const taxes = parseFloat((vp * (parsedTaxRate / 100)).toFixed(4));

    // 3. Commission = VP * commissionRate%
    const commission = parseFloat((vp * (parsedCommissionRate / 100)).toFixed(4));

    // 4. Contribution Margin (Numerator)
    const absoluteMargin = parseFloat((vp - taxes - commission - parsedFreight).toFixed(4));

    // 5. CM = Absolute Margin / Costs
    const marginRatio = parseFloat((absoluteMargin / parsedCosts).toFixed(6));
    const marginPercentage = parseFloat((marginRatio * 100).toFixed(4));

    // Badge styling thresholds:
    // Red (< 10% or negative)
    // Orange (< 19%)
    // Yellow (< 30%)
    // Green (>= 30%)
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
        margin: marginPercentage, // internal high precision
        badgeColor,
        formattedMargin,
        breakdown: {
            gross: parseFloat(parsedGross.toFixed(4)),
            vp: vp,
            vpDiscount: parseFloat((parsedGross - vp).toFixed(4)),
            taxes: taxes,
            commission: commission,
            freight: parseFloat(parsedFreight.toFixed(4)),
            costs: parseFloat(parsedCosts.toFixed(4)),
            absoluteMargin: absoluteMargin
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
    let hasPendingCost = false;

    // Sum up items
    po.items.forEach(item => {
        const qty = parseInt(item.quantity) || 0;
        if (qty <= 0) return;

        // Try standard fields or fallback to extra_metadata
        const unitCost = 
            parseFloat(item.total_cost) || 
            parseFloat(item.cost_mp) || 
            parseFloat(item.extra_metadata?.total_cost) || 
            parseFloat(item.extra_metadata?.cost_mp) || 
            0;

        if (unitCost <= 0) {
            hasPendingCost = true;
        }

        const priceUnit = 
            parseFloat(item.unit_value) || 
            parseFloat(item.price_unit) || 
            parseFloat(item.price) || 
            0;

        const itemGross = priceUnit * qty;
        const days = parsePaymentTermsToDays(item.payment_terms || po.payment_terms || po.extra_metadata?.payment_terms);
        
        const vpFactor = Math.pow(1.025, days / 30);
        const itemVP = itemGross / vpFactor;
        const itemTaxes = itemVP * 0.0925;  // FF-HARDENING-015: PIS/COFINS 9.25% (was 0.2225)

        // Try getting commission rate from item or PO
        const commissionRate = 
            parseFloat(item.manual_commission_rate) || 
            parseFloat(item.extra_metadata?.manual_commission_rate) || 
            parseFloat(po.commission_rate) || 
            0;
        
        const itemCommission = itemVP * (commissionRate / 100);
        const itemFreight = parseFloat(item.freight) || 0;

        totalGross += itemGross;
        totalVP += itemVP;
        totalTaxes += itemTaxes;
        totalCommission += itemCommission;
        totalFreight += itemFreight;
        totalCosts += (unitCost * qty);
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
    const marginRatio = parseFloat((totalAbsoluteMargin / totalCosts).toFixed(6));
    const marginPercentage = parseFloat((marginRatio * 100).toFixed(4));

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
        margin: marginPercentage,
        badgeColor,
        formattedMargin,
        breakdown: {
            gross: totalGross,
            vp: totalVP,
            vpDiscount: parseFloat((totalGross - totalVP).toFixed(4)),
            taxes: totalTaxes,
            commission: totalCommission,
            freight: totalFreight,
            costs: totalCosts,
            absoluteMargin: totalAbsoluteMargin
        }
    };
}
