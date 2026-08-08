from fastapi.testclient import TestClient

from app.main import app

BROWSER_ORIGIN = "http://localhost:5173"


def test_health_is_public() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200


def test_cors_preflight_needs_no_token() -> None:
    """Preflight OPTIONS requests carry no Authorization header by design,
    so they must be answered before the auth middleware can reject them."""
    response = TestClient(app).options(
        "/goals",
        headers={
            "Origin": BROWSER_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == BROWSER_ORIGIN
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_cors_headers_ride_along_on_rejections(client: TestClient) -> None:
    """Even a 401 needs the CORS header, or the browser hides the real
    status from the frontend and the token gate cannot react to it."""
    response = TestClient(app).get("/goals", headers={"Origin": BROWSER_ORIGIN})
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == BROWSER_ORIGIN


def test_unknown_origins_get_no_cors_headers() -> None:
    response = TestClient(app).get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_missing_token_is_rejected() -> None:
    response = TestClient(app).get("/goals")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_wrong_token_is_rejected() -> None:
    response = TestClient(app).get("/goals", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def test_wrong_scheme_is_rejected() -> None:
    response = TestClient(app).get("/goals", headers={"Authorization": "Basic test-token"})
    assert response.status_code == 401


def test_correct_token_is_accepted(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
