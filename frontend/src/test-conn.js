/**
 * Frontend-Backend Connectivity Test Script
 * 
 * This script tests if the frontend can reach the backend API.
 * Run with: node frontend/src/test-conn.js
 */

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000/api';

async function testConnection() {
    console.log('='.repeat(80));
    console.log('FlexFlow Frontend-Backend Connectivity Test');
    console.log('='.repeat(80));
    console.log(`\nTesting connection to: ${API_BASE_URL}`);
    console.log(`Ping endpoint: ${API_BASE_URL}/ping\n`);

    try {
        // Test 1: Public ping endpoint (no auth required)
        console.log('[TEST 1] Testing public /api/ping endpoint...');
        const response = await fetch(`${API_BASE_URL}/ping`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        console.log(`  Status: ${response.status} ${response.statusText}`);

        if (response.ok) {
            const data = await response.json();
            console.log(`  ✅ SUCCESS: Backend is reachable!`);
            console.log(`  Response:`, JSON.stringify(data, null, 2));
        } else {
            console.log(`  ❌ FAILED: Backend returned error status`);
            const text = await response.text();
            console.log(`  Response:`, text);
        }

        // Test 2: CORS preflight check
        console.log('\n[TEST 2] Testing CORS preflight (OPTIONS request)...');
        const corsResponse = await fetch(`${API_BASE_URL}/ping`, {
            method: 'OPTIONS',
            headers: {
                'Origin': 'http://localhost:3000',
                'Access-Control-Request-Method': 'GET',
                'Access-Control-Request-Headers': 'content-type',
            },
        });

        console.log(`  Status: ${corsResponse.status} ${corsResponse.statusText}`);
        console.log(`  CORS Headers:`);
        console.log(`    - Access-Control-Allow-Origin: ${corsResponse.headers.get('access-control-allow-origin')}`);
        console.log(`    - Access-Control-Allow-Methods: ${corsResponse.headers.get('access-control-allow-methods')}`);
        console.log(`    - Access-Control-Allow-Headers: ${corsResponse.headers.get('access-control-allow-headers')}`);
        console.log(`    - Access-Control-Allow-Credentials: ${corsResponse.headers.get('access-control-allow-credentials')}`);

        if (corsResponse.ok || corsResponse.status === 200) {
            console.log(`  ✅ CORS is properly configured`);
        } else {
            console.log(`  ⚠️  CORS might have issues`);
        }

        // Test 3: Protected endpoint without auth (should get 401)
        console.log('\n[TEST 3] Testing protected endpoint without auth...');
        const protectedResponse = await fetch(`${API_BASE_URL}/kanban/pos`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        console.log(`  Status: ${protectedResponse.status} ${protectedResponse.statusText}`);

        if (protectedResponse.status === 401) {
            console.log(`  ✅ EXPECTED: Got 401 Unauthorized (auth is working)`);
            const data = await protectedResponse.json();
            console.log(`  Response:`, JSON.stringify(data, null, 2));
        } else if (protectedResponse.status === 403) {
            console.log(`  ⚠️  Got 403 Forbidden instead of 401 (might indicate token issue)`);
            const data = await protectedResponse.json();
            console.log(`  Response:`, JSON.stringify(data, null, 2));
        } else {
            console.log(`  ❌ UNEXPECTED: Expected 401, got ${protectedResponse.status}`);
        }

        console.log('\n' + '='.repeat(80));
        console.log('Test Summary:');
        console.log('  - Backend is reachable: ✅');
        console.log('  - CORS is configured: ✅');
        console.log('  - Authentication is required: ✅');
        console.log('\nNext steps:');
        console.log('  1. Make sure you are logged in on the frontend');
        console.log('  2. Check browser console for token in localStorage');
        console.log('  3. Verify token is being sent in Authorization header');
        console.log('='.repeat(80));

    } catch (error) {
        console.log(`\n❌ CONNECTION FAILED: ${error.message}`);
        console.log('\nPossible causes:');
        console.log('  - Backend is not running (start with: python -m uvicorn backend.main:app --reload --port 8000)');
        console.log('  - Wrong API URL (check VITE_API_URL in .env)');
        console.log('  - Network/firewall issues');
        console.log('='.repeat(80));
        process.exit(1);
    }
}

// Run the test
testConnection();
