from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_security_headers_injected():
    response = client.get("/api/ping")
    assert response.status_code == 200
    headers = response.headers
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"
    assert "default-src 'self'" in headers.get("Content-Security-Policy", "")

def test_security_scanner_probes_blocked():
    probe_paths = ["/wp-admin", "/wp-content/plugins", "/backup.zip", "/database/sql", "/db/dump", "/logs/app.log", "/config.env", "/config/db.env"]
    for path in probe_paths:
        response = client.get(path)
        assert response.status_code == 404

def test_legitimate_configuracoes_route_allowed():
    response = client.get("/configuracoes")
    assert response.status_code == 200
