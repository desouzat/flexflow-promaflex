@echo off
REM FlexFlow Stress Test Runner (Windows)
REM ========================================

echo.
echo ================================================================================
echo FlexFlow - Stress ^& Journey Test Integrado
echo ================================================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.8+
    pause
    exit /b 1
)

echo [INFO] Checking server health...
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Server is not running!
    echo [INFO] Please start the server first:
    echo        cd backend
    echo        uvicorn main:app --reload
    echo.
    pause
    exit /b 1
)

echo [SUCCESS] Server is running
echo.

REM Install dependencies if needed
echo [INFO] Checking dependencies...
pip show requests >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install -r requirements_stress_test.txt
)

echo.
echo ================================================================================
echo WARNING: This test will simulate errors and stress the system!
echo ================================================================================
echo.
echo Press Ctrl+C to cancel, or
pause

echo.
echo [INFO] Starting stress test...
echo.

REM Run the test
python -m backend.tests.stress_test_journey

echo.
echo ================================================================================
echo Test completed! Check stress_test_report.json for detailed results.
echo ================================================================================
echo.
pause
