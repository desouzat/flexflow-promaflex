import { calculatePackagingProductionArea, parseBrazilianFloat } from '../src/utils/packagingCalculator.js';

console.log('='.repeat(100));
console.log('🔬 HARNESS DE TESTE MATEMÁTICO EMPÍRICO — CALCULADORA UNIT-AWARE (CR-F5 EXTENSION)');
console.log('='.repeat(100));

const testVectors = [
    {
        name: 'Vetor 1: CSN Apontamento Direto M²',
        sku: '2545',
        unit: 'M2',
        widthMm: 1222,
        lengthM: 6000,
        m2Mode: 'direct_m2',
        input: '10000',
        expectedArea: 10000.00,
        legacyCatastrophicArea: 73320000.00
    },
    {
        name: 'Vetor 2: CSN Bobina Variável 1 (Metros Lineares)',
        sku: '2545',
        unit: 'M2',
        widthMm: 1222,
        lengthM: 6000,
        m2Mode: 'linear_meters',
        input: '4000',
        expectedArea: 4888.00,
        legacyCatastrophicArea: 29328000.00
    },
    {
        name: 'Vetor 3: CSN Bobina Variável 2 (Metros Lineares)',
        sku: '2545',
        unit: 'M2',
        widthMm: 1222,
        lengthM: 6000,
        m2Mode: 'linear_meters',
        input: '3800',
        expectedArea: 4643.60,
        legacyCatastrophicArea: 27861600.00
    },
    {
        name: 'Vetor 4: Rolo Padrão Fita (RL)',
        sku: 'PROMATAPE',
        unit: 'RL',
        widthMm: 1200,
        lengthM: 50,
        m2Mode: null,
        input: '5',
        expectedArea: 300.00,
        legacyCatastrophicArea: null
    },
    {
        name: 'Vetor 5: Metro Linear (M/ML)',
        sku: 'LINEAR-1000',
        unit: 'M',
        widthMm: 1000,
        lengthM: null,
        m2Mode: null,
        input: '250',
        expectedArea: 250.00,
        legacyCatastrophicArea: null
    }
];

let allPassed = true;

console.log(`\n${'VETOR'.padEnd(48)} | ${'UNIDADE'.padEnd(7)} | ${'MODO'.padEnd(14)} | ${'INPUT'.padEnd(7)} | ${'ESPERADO'.padEnd(12)} | ${'OBTIDO'.padEnd(12)} | STATUS`);
console.log('-'.repeat(115));

for (const vec of testVectors) {
    const res = calculatePackagingProductionArea({
        unit: vec.unit,
        widthMm: vec.widthMm,
        lengthM: vec.lengthM,
        m2Mode: vec.m2Mode,
        input: vec.input
    });

    const diff = Math.abs(res.calculatedAreaM2 - vec.expectedArea);
    const passed = diff < 0.001;
    if (!passed) allPassed = false;

    const statusBadge = passed ? '✅ PASS' : '❌ FAIL';
    console.log(
        `${vec.name.padEnd(48)} | ` +
        `${vec.unit.padEnd(7)} | ` +
        `${(vec.m2Mode || 'standard').padEnd(14)} | ` +
        `${vec.input.padEnd(7)} | ` +
        `${(vec.expectedArea.toFixed(2) + ' m²').padEnd(12)} | ` +
        `${(res.calculatedAreaM2.toFixed(2) + ' m²').padEnd(12)} | ` +
        `${statusBadge}`
    );
    console.log(`   └─ ℹ️ Detalhe da Fórmula: ${res.calcExplanation}`);
    if (vec.legacyCatastrophicArea) {
        console.log(`   └─ 🛡️ Defesa Contra Erro Legado: ${res.calculatedAreaM2.toFixed(2)} m² vs Erro Antigo de ${vec.legacyCatastrophicArea.toLocaleString('pt-BR')} m²`);
    }
    console.log();
}

console.log('='.repeat(100));
if (allPassed) {
    console.log('🎉 TODOS OS 5 VETORES MATEMÁTICOS FORAM HOMOLOGADOS COM 100% DE SUCESSO!');
    process.exit(0);
} else {
    console.error('❌ FALHA DETECTADA EM UM OU MAIS VETORES MATEMÁTICOS!');
    process.exit(1);
}
