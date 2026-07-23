from fastapi.testclient import TestClient

from app.main import app


def test_health_is_public() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200


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
