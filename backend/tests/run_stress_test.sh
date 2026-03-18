#!/bin/bash
# FlexFlow Stress Test Runner (Linux/Mac)
# ========================================

echo ""
echo "================================================================================"
echo "FlexFlow - Stress & Journey Test Integrado"
echo "================================================================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found! Please install Python 3.8+"
    exit 1
fi

echo "[INFO] Checking server health..."
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "[ERROR] Server is not running!"
    echo "[INFO] Please start the server first:"
    echo "       cd backend"
    echo "       uvicorn main:app --reload"
    echo ""
    exit 1
fi

echo "[SUCCESS] Server is running"
echo ""

# Install dependencies if needed
echo "[INFO] Checking dependencies..."
if ! python3 -c "import requests" &> /dev/null; then
    echo "[INFO] Installing dependencies..."
    pip3 install -r requirements_stress_test.txt
fi

echo ""
echo "================================================================================"
echo "WARNING: This test will simulate errors and stress the system!"
echo "================================================================================"
echo ""
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

echo ""
echo "[INFO] Starting stress test..."
echo ""

# Run the test
python3 -m backend.tests.stress_test_journey

echo ""
echo "================================================================================"
echo "Test completed! Check stress_test_report.json for detailed results."
echo "================================================================================"
echo ""
