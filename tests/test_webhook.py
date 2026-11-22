"""Tests del webhook de productos y de la autenticación JWT de la API."""
from __future__ import annotations

import time

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

import eia_ingest.security as security
from eia_ingest import api

TEST_SECRET = "test-secret-0123456789abcdef0123456789abcdef"


def make_token(secret: str = TEST_SECRET, **claims) -> str:
    payload = {"sub": "vendure", "exp": int(time.time()) + 3600, **claims}
    return pyjwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def calls(monkeypatch):
    """Captura las acciones despachadas sin tocar PostgreSQL/Qdrant."""
    recorded = {"sync": [], "delete": []}
    monkeypatch.setattr(
        api,
        "sync_catalog",
        lambda product_id=None: recorded["sync"].append(product_id)
        or {"status": "completed"},
    )
    monkeypatch.setattr(
        api,
        "delete_product",
        lambda product_id: recorded["delete"].append(product_id)
        or {"status": "completed"},
    )
    return recorded


@pytest.fixture
def client(monkeypatch, calls):
    monkeypatch.setattr(security, "JWT_SECRET", TEST_SECRET)
    return TestClient(api.app)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------


def test_missing_token_returns_401(client):
    response = client.post("/webhooks/product", json={"event": "created", "product_id": 1})
    assert response.status_code == 401


def test_invalid_signature_returns_401(client):
    token = make_token(secret="otro-secreto-0123456789abcdef0123456789")
    response = client.post(
        "/webhooks/product",
        json={"event": "created", "product_id": 1},
        headers=auth(token),
    )
    assert response.status_code == 401


def test_expired_token_returns_401(client):
    token = pyjwt.encode(
        {"sub": "vendure", "exp": int(time.time()) - 10},
        TEST_SECRET,
        algorithm="HS256",
    )
    response = client.post(
        "/webhooks/product",
        json={"event": "created", "product_id": 1},
        headers=auth(token),
    )
    assert response.status_code == 401


def test_missing_secret_fails_closed(client, monkeypatch):
    monkeypatch.setattr(security, "JWT_SECRET", "")
    response = client.post(
        "/webhooks/product",
        json={"event": "created", "product_id": 1},
        headers=auth(make_token()),
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Webhook: despacho de eventos
# ---------------------------------------------------------------------------


def test_webhook_created_dispatches_sync(client, calls):
    response = client.post(
        "/webhooks/product",
        json={"event": "created", "product_id": 42},
        headers=auth(make_token()),
    )
    assert response.status_code == 202
    body = response.json()
    assert body["event"] == "created"
    assert body["product_id"] == 42
    assert calls["sync"] == [42]
    assert calls["delete"] == []


def test_webhook_updated_dispatches_sync(client, calls):
    response = client.post(
        "/webhooks/product",
        json={"event": "updated", "product_id": 7, "tenant_id": "platform"},
        headers=auth(make_token()),
    )
    assert response.status_code == 202
    assert calls["sync"] == [7]


def test_webhook_deleted_dispatches_delete(client, calls):
    response = client.post(
        "/webhooks/product",
        json={"event": "deleted", "product_id": 99},
        headers=auth(make_token()),
    )
    assert response.status_code == 202
    assert calls["delete"] == [99]
    assert calls["sync"] == []


def test_webhook_invalid_event_returns_422(client, calls):
    response = client.post(
        "/webhooks/product",
        json={"event": "archived", "product_id": 1},
        headers=auth(make_token()),
    )
    assert response.status_code == 422
    assert calls["sync"] == [] and calls["delete"] == []


def test_webhook_missing_product_id_returns_422(client):
    response = client.post(
        "/webhooks/product",
        json={"event": "created"},
        headers=auth(make_token()),
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Endpoints existentes protegidos
# ---------------------------------------------------------------------------


PROTECTED_POSTS = [
    ("/sync", {}),
    ("/sync/product/1", {}),
    ("/sync/documents", {}),
    ("/sync/ui-guides", {}),
]


@pytest.mark.parametrize("path,body", PROTECTED_POSTS)
def test_protected_endpoints_require_token(client, path, body):
    response = client.post(path, json=body)
    assert response.status_code == 401


@pytest.mark.parametrize("path,body", PROTECTED_POSTS)
def test_protected_endpoints_accept_valid_token(client, path, body):
    response = client.post(path, json=body, headers=auth(make_token()))
    assert response.status_code == 202


def test_root_stays_public(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"
