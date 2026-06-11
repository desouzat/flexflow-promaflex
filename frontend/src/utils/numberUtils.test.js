import { describe, it, expect } from 'vitest'
import { cleanBrazilianNumber } from './numberUtils'

describe('cleanBrazilianNumber', () => {
    it('should handle currency prefix R$ with spaces', () => {
        expect(cleanBrazilianNumber('R$ 1.000,00')).toBe(1000.0)
    })

    it('should handle plain Brazilian format', () => {
        expect(cleanBrazilianNumber('1.250,50')).toBe(1250.5)
    })

    it('should handle high precision (6 decimals)', () => {
        expect(cleanBrazilianNumber('108.753,123456')).toBe(108753.123456)
    })

    it('should return number verbatim if input is already a number', () => {
        expect(cleanBrazilianNumber(1250.5)).toBe(1250.5)
        expect(cleanBrazilianNumber(0)).toBe(0)
    })

    it('should handle null/undefined/empty string by returning 0.0', () => {
        expect(cleanBrazilianNumber(null)).toBe(0.0)
        expect(cleanBrazilianNumber(undefined)).toBe(0.0)
        expect(cleanBrazilianNumber('')).toBe(0.0)
        expect(cleanBrazilianNumber('   ')).toBe(0.0)
        expect(cleanBrazilianNumber('N/A')).toBe(0.0)
    })

    it('should handle negative numbers by returning 0.0', () => {
        expect(cleanBrazilianNumber('-100')).toBe(0.0)
        expect(cleanBrazilianNumber(-100.0)).toBe(0.0)
    })

    it('should strip dollar prefix correctly', () => {
        expect(cleanBrazilianNumber('$ 500,00')).toBe(500.0)
    })

    it('should handle millions with multiple dots', () => {
        expect(cleanBrazilianNumber('1.000.000,00')).toBe(1000000.0)
    })
})
