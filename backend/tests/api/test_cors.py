"""CORS: only the site URL and the Capacitor origin, only on /api."""

from __future__ import annotations

from fastapi.testclient import TestClient

SITE = "https://cendekiara.test"
CAPACITOR = "capacitor://localhost"
OTHER = "https://somewhere.else"


def test_the_site_origin_is_allowed(api_client: TestClient) -> None:
    response = api_client.get("/api/commands", headers={"Origin": SITE})
    assert response.headers["access-control-allow-origin"] == SITE


def test_the_capacitor_origin_is_allowed(api_client: TestClient) -> None:
    response = api_client.get("/api/commands", headers={"Origin": CAPACITOR})
    assert response.headers["access-control-allow-origin"] == CAPACITOR


def test_another_origin_is_not_allowed(api_client: TestClient) -> None:
    response = api_client.get("/api/commands", headers={"Origin": OTHER})
    assert "access-control-allow-origin" not in response.headers


def test_no_origin_means_no_cors_headers(api_client: TestClient) -> None:
    response = api_client.get("/api/commands")
    assert "access-control-allow-origin" not in response.headers


def test_a_preflight_is_answered_for_an_allowed_origin(api_client: TestClient) -> None:
    response = api_client.options(
        "/api/commands/system.health",
        headers={
            "Origin": SITE,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == SITE


def test_cors_is_only_on_the_api(api_client: TestClient) -> None:
    response = api_client.get("/not-the-api", headers={"Origin": SITE})
    assert response.status_code == 404
    assert "access-control-allow-origin" not in response.headers
