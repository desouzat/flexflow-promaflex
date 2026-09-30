import { describe, it, expect } from 'vitest';
import {
    calculatePackagingProductionArea,
    parseBrazilianFloat,
    normalizePoUnit
} from '../utils/packagingCalculator';

describe('Unit-Aware Packaging Calculator (CR-F5 Extension)', () => {
    // Vector 1 (CSN Direct M²)
    it('Vector 1: CSN Direct M² produces exactly 10000.00 m² and NOT 73,320,000 m²', () => {
        const result = calculatePackagingProductionArea({
            unit: 'M2',
            widthMm: 1222,
            lengthM: 6000,
            m2Mode: 'direct_m2',
            input: '10000'
        });

        expect(result.calculatedAreaM2).toBe(10000);
        expect(result.calculatedAreaM2).not.toBe(73320000);
        expect(result.calcExplanation).toContain('10000.00 m²');
    });

    // Vector 2 (CSN Variable Coil 1 - Linear Meters)
    it('Vector 2: CSN Variable Coil 1 (4000m linear) calculates 4888.00 m²', () => {
        const result = calculatePackagingProductionArea({
            unit: 'M2',
            widthMm: 1222,
            lengthM: 6000,
            m2Mode: 'linear_meters',
            input: '4000'
        });

        // 4000 * (1222 / 1000) = 4000 * 1.222 = 4888.00
        expect(result.calculatedAreaM2).toBeCloseTo(4888.00, 2);
    });

    // Vector 3 (CSN Variable Coil 2 - Linear Meters)
    it('Vector 3: CSN Variable Coil 2 (3800m linear) calculates 4643.60 m²', () => {
        const result = calculatePackagingProductionArea({
            unit: 'M2',
            widthMm: 1222,
            lengthM: 6000,
            m2Mode: 'linear_meters',
            input: '3800'
        });

        // 3800 * (1222 / 1000) = 3800 * 1.222 = 4643.60
        expect(result.calculatedAreaM2).toBeCloseTo(4643.60, 2);
    });

    // Vector 4 (Standard Roll RL)
    it('Vector 4: Standard Roll RL (5 rolls of 1200mm x 50m) calculates 300.00 m²', () => {
        const result = calculatePackagingProductionArea({
            unit: 'RL',
            widthMm: 1200,
            lengthM: 50,
            input: '5'
        });

        // unitArea = (1200 / 1000) * 50 = 1.2 * 50 = 60 m²
        // 5 * 60 = 300 m²
        expect(result.unitAreaM2).toBeCloseTo(60.0, 2);
        expect(result.calculatedAreaM2).toBeCloseTo(300.00, 2);
    });

    // Vector 5 (Linear Meter ML / M)
    it('Vector 5: Linear Meter ML / M (250m with 1000mm width) calculates 250.00 m²', () => {
        const result = calculatePackagingProductionArea({
            unit: 'M',
            widthMm: 1000,
            input: '250'
        });

        // 250 * (1000 / 1000) = 250 * 1.0 = 250 m²
        expect(result.calculatedAreaM2).toBeCloseTo(250.00, 2);
    });

    // Brazilian comma decimal parsing test
    it('Brazilian decimal parsing handles commas and dots cleanly', () => {
        expect(parseBrazilianFloat('10.000,50')).toBe(10000.5);
        expect(parseBrazilianFloat('4000,5')).toBe(4000.5);
        expect(parseBrazilianFloat('1222')).toBe(1222);
    });

    // Unit normalization test
    it('normalizePoUnit extracts unit from various item fields', () => {
        expect(normalizePoUnit({ unit: 'M2' })).toBe('M2');
        expect(normalizePoUnit({ unidade_medida: 'm2' })).toBe('M2');
        expect(normalizePoUnit({}, { 'Un. Med.': 'RL' })).toBe('RL');
        expect(normalizePoUnit({}, {})).toBe('UN');
    });
});
