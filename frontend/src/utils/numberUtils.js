/**
 * Normalizes a Brazilian formatted currency or numeric string into a standard JS Number.
 * Handles cases like 'R$ 1.000,00', '1.250,50', and '108.753,123456'.
 * Returns 0.0 for invalid/null/undefined/negative inputs.
 * 
 * @param {any} value
 * @returns {number}
 */
export function cleanBrazilianNumber(value) {
    if (value === null || value === undefined) {
        return 0.0;
    }

    if (typeof value === 'number') {
        if (isNaN(value) || !isFinite(value)) {
            return 0.0;
        }
        return value < 0.0 ? 0.0 : value;
    }

    try {
        let cleaned = String(value).trim();
        
        // Remove currency symbols (R$ or $)
        cleaned = cleaned.replace(/R\$/gi, '').replace(/\$/g, '');
        
        // Strip whitespace
        cleaned = cleaned.replace(/\s+/g, '');

        if (!cleaned || cleaned.toUpperCase() === 'N/A') {
            return 0.0;
        }

        // Keep only digits, dots, commas, and minus sign
        cleaned = cleaned.replace(/[^0-9.,-]/g, '');

        if (!cleaned) {
            return 0.0;
        }

        const hasComma = cleaned.includes(',');
        const dotCount = (cleaned.match(/\./g) || []).length;

        if (hasComma) {
            // dots are thousands separators, comma is decimal separator
            cleaned = cleaned.replace(/\./g, '').replace(',', '.');
        } else if (dotCount > 1) {
            // multiple dots are all thousands separators
            cleaned = cleaned.replace(/\./g, '');
        }

        const parsed = parseFloat(cleaned);
        if (isNaN(parsed) || !isFinite(parsed)) {
            return 0.0;
        }

        // Reject negative numbers
        if (parsed < 0.0) {
            return 0.0;
        }

        return parsed;
    } catch (e) {
        return 0.0;
    }
}
