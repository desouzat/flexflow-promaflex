@echo off
REM FlexFlow API Connectivity Test Script for Windows
REM Tests backend connectivity and CORS configuration

echo ================================================================================
echo FlexFlow Backend Connectivity Test
echo ================================================================================
echo.

echo [TEST 1] Testing public /api/ping endpoint (no auth required)...
curl -v -X GET http://localhost:8000/api/ping
echo.
echo.

echo [TEST 2] Testing CORS preflight (OPTIONS request)...
curl -v -X OPTIONS http://localhost:8000/api/ping ^
  -H "Origin: http://localhost:3000" ^
  -H "Access-Control-Request-Method: GET" ^
  -H "Access-Control-Request-Headers: content-type,authorization"
echo.
echo.

echo [TEST 3] Testing protected endpoint without auth (should get 401)...
curl -v -X GET http://localhost:8000/api/kanban/pos ^
  -H "Origin: http://localhost:3000"
echo.
echo.

echo ================================================================================
echo Test Complete
echo ================================================================================
echo.
echo If all tests passed:
echo   - Backend is running and reachable
echo   - CORS is properly configured
echo   - Authentication is working
echo.
echo Next: Check browser console to see if token is in localStorage
echo.
pause
