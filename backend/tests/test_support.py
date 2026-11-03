"""Tests de soporte: cambiar contraseña, link para restablecerla y panel del administrador."""

import datetime as dt

import pytest
from sqlmodel import select

from backend.app.config import get_settings
from backend.app.models import PasswordReset
from backend.tests.conftest import PASSWORD


@pytest.fixture
def admin(make_user, monkeypatch):
    """Un administrador (su email está en ADMIN_EMAILS)."""
    monkeypatch.setattr(get_settings(), "admin_emails", "jefe@example.com")
    return make_user("jefe@example.com")


def login(client, email, password):
    return client.post("/api/auth/login", data={"username": email, "password": password})


def test_cambiar_contrasena(client, auth):
    mal = client.post("/api/users/me/password", json={"current_password": "otra-cosa", "new_password": "nueva-clave-123"},
                      headers=auth)
    assert mal.status_code == 400
    ok = client.post("/api/users/me/password", json={"current_password": PASSWORD, "new_password": "nueva-clave-123"},
                     headers=auth)
    assert ok.status_code == 204
    assert login(client, "ana@example.com", "nueva-clave-123").status_code == 200
    assert login(client, "ana@example.com", PASSWORD).status_code == 401


def test_tutorial_solo_la_primera_vez(client, auth):
    # Cuenta nueva: el tutorial está pendiente; al marcarlo, queda guardado en la cuenta
    assert client.get("/api/users/me", headers=auth).json()["tour_done"] is False
    client.patch("/api/users/me", json={"tour_done": True}, headers=auth)
    assert client.get("/api/users/me", headers=auth).json()["tour_done"] is True


def test_link_para_restablecer(client, make_user, admin):
    ana = make_user("ana@example.com")
    ana_id = client.get("/api/users/me", headers=ana).json()["id"]
    # Solo el administrador puede generar links
    assert client.post(f"/api/admin/users/{ana_id}/reset-link", headers=ana).status_code == 403
    url = client.post(f"/api/admin/users/{ana_id}/reset-link", headers=admin).json()["url"]
    token = url.split("token=")[1]
    assert "/restablecer.html?token=" in url
    assert client.post("/api/auth/reset", json={"token": token, "new_password": "olvidada-no-mas"}).status_code == 204
    assert login(client, "ana@example.com", "olvidada-no-mas").status_code == 200
    # Es de un solo uso
    assert client.post("/api/auth/reset", json={"token": token, "new_password": "otra-mas-123"}).status_code == 400
    assert client.post("/api/auth/reset", json={"token": "x" * 40, "new_password": "otra-mas-123"}).status_code == 400


def test_el_link_vence(client, make_user, admin, session):
    ana = make_user("ana@example.com")
    ana_id = client.get("/api/users/me", headers=ana).json()["id"]
    token = client.post(f"/api/admin/users/{ana_id}/reset-link", headers=admin).json()["url"].split("token=")[1]
    reset = session.exec(select(PasswordReset)).first()
    reset.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    session.add(reset)
    session.commit()
    assert client.post("/api/auth/reset", json={"token": token, "new_password": "tarde-123"}).status_code == 400


def test_panel_solo_estadisticas_y_datos_con_permiso(client, make_user, admin):
    ana = make_user("ana@example.com")
    client.post("/api/expenses", json={"category": "food", "amount_cents": 12_345, "description": "secreto"}, headers=ana)
    assert client.get("/api/admin/users", headers=ana).status_code == 403
    usuarios = {u["email"]: u for u in client.get("/api/admin/users", headers=admin).json()}
    fila = usuarios["ana@example.com"]
    assert fila["expenses"] == 1 and fila["last_activity"] is not None
    assert "12345" not in str(fila) and "secreto" not in str(fila)          # sin montos ni descripciones
    # Sin permiso no se ven sus datos…
    assert client.get(f"/api/admin/users/{fila['id']}/data", headers=admin).status_code == 403
    # …con permiso sí
    me = client.patch("/api/users/me", json={"shares_data": True}, headers=ana).json()
    assert me["shares_data"] is True and me["is_admin"] is False
    datos = client.get(f"/api/admin/users/{fila['id']}/data", headers=admin).json()
    assert datos["expenses"][0]["description"] == "secreto"


def test_comentarios(client, make_user, admin):
    ana = make_user("ana@example.com")
    assert client.post("/api/users/me/feedback", json={"message": "No entendí el plan", "page": "/metas.html"},
                       headers=ana).status_code == 201
    lista = client.get("/api/admin/feedback", headers=admin).json()
    assert lista[0]["message"] == "No entendí el plan" and lista[0]["email"] == "ana@example.com"
    # Borrar la cuenta borra también sus comentarios
    assert client.delete("/api/users/me", headers=ana).status_code == 204
    assert client.get("/api/admin/feedback", headers=admin).json() == []


def test_soy_admin(client, admin):
    assert client.get("/api/users/me", headers=admin).json()["is_admin"] is True
