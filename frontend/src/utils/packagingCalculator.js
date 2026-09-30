/**
 * FlexFlow - Unit-Aware Packaging Area Calculator Engine
 * CR-F5 Extension: Support for Variable Length Coils (CSN), Linear Meters, and Direct M2.
 */

export const parseBrazilianFloat = (val) => {
    if (val === null || val === undefined) return 0;
    if (typeof val === 'number') return isNaN(val) ? 0 : val;
    let clean = String(val).trim().replace(/\s+/g, '');
    const hasComma = clean.includes(',');
    const dotCount = (clean.match(/\./g) || []).length;
    if (hasComma) {
        clean = clean.replace(/\./g, '').replace(',', '.');
    } else if (dotCount > 1) {
        clean = clean.replace(/\./g, '');
    }
    const num = parseFloat(clean);
    return isNaN(num) ? 0 : num;
};

export const normalizePoUnit = (item, iMeta = {}) => {
    return (
        item?.unit ||
        item?.unidade_medida ||
        iMeta?.unit ||
        iMeta?.unidade_medida ||
        iMeta?.['Un. Med.'] ||
        iMeta?.['Unidade'] ||
        'UN'
    ).toString().toUpperCase().trim();
};

export const isM2Unit = (unit) => ['M2', 'M²', 'METRO QUADRADO', 'METROS QUADRADOS'].includes((unit || '').toString().toUpperCase().trim());
export const isLinearUnit = (unit) => ['M', 'ML', 'METRO', 'METROS', 'METRO LINEAR', 'METROS LINEARES'].includes((unit || '').toString().toUpperCase().trim());
export const isRollUnit = (unit) => ['RL', 'UN', 'PC', 'PÇ', 'ROLO', 'ROLOS', 'BOBINA', 'BOBINAS', 'PECAS', 'PEÇAS', 'PECA', 'PEÇA', 'UND', 'UNID'].includes((unit || '').toString().toUpperCase().trim());

/**
 * Calculates packaging area in m² based on unit type and operator input.
 *
 * @param {Object} params
 * @param {string} params.unit - Normalized PO unit (e.g. 'M2', 'RL', 'M')
 * @param {number|string} params.widthMm - Width in millimeters
 * @param {number|string} params.lengthM - Length in meters
 * @param {string} [params.m2Mode='linear_meters'] - Mode for M2 units: 'linear_meters' | 'direct_m2'
 * @param {number|string} params.input - Operator input value
 * @returns {{ calculatedAreaM2: number, calcExplanation: string, unitAreaM2: number|null }}
 */
export function calculatePackagingProductionArea({
    unit,
    widthMm: rawWidth,
    lengthM: rawLength,
    m2Mode = 'linear_meters',
    input: rawInput
}) {
    const widthMm = parseBrazilianFloat(rawWidth);
    const lengthM = parseBrazilianFloat(rawLength);
    const inputValue = parseBrazilianFloat(rawInput);
    const poUnit = (unit || 'UN').toString().toUpperCase().trim();

    const hasDimensions = widthMm > 0 && lengthM > 0;
    const unitAreaM2 = hasDimensions ? (widthMm / 1000.0) * lengthM : null;

    let calculatedAreaM2 = 0;
    let calcExplanation = '';

    if (isM2Unit(poUnit)) {
        if (m2Mode === 'direct_m2') {
            calculatedAreaM2 = inputValue > 0 ? inputValue : 0;
            calcExplanation = `Entrada direta: ${calculatedAreaM2.toFixed(2)} m²`;
        } else {
            // linear_meters: metros da bobina * (largura_mm / 1000)
            const widthM = widthMm > 0 ? (widthMm / 1000.0) : 0;
            calculatedAreaM2 = (inputValue > 0 && widthM > 0) ? (inputValue * widthM) : 0;
            calcExplanation = `${inputValue} m × ${widthM.toFixed(4)} m = ${calculatedAreaM2.toFixed(2)} m²`;
        }
    } else if (isLinearUnit(poUnit)) {
        const widthM = widthMm > 0 ? (widthMm / 1000.0) : 0;
        calculatedAreaM2 = (inputValue > 0 && widthM > 0) ? (inputValue * widthM) : 0;
        calcExplanation = `${inputValue} m × ${widthM.toFixed(4)} m = ${calculatedAreaM2.toFixed(2)} m²`;
    } else {
        // Roll count mode (RL, UN, etc.)
        calculatedAreaM2 = (inputValue > 0 && unitAreaM2) ? (inputValue * unitAreaM2) : 0;
        calcExplanation = `${inputValue} bobinas × ${unitAreaM2?.toFixed(2)} m² = ${calculatedAreaM2.toFixed(2)} m²`;
    }

    return {
        calculatedAreaM2,
        calcExplanation,
        unitAreaM2
    };
}
