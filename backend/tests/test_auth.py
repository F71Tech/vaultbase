"""Tests de registro, login y perfil."""

from .conftest import PASSWORD


def test_registro_no_devuelve_la_contrasena(client):
    res = client.post(
        "/api/auth/register",
        json={"email": "Ana@Example.com", "name": "Ana", "password": PASSWORD},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "ana@example.com"  # el email se normaliza a minúsculas
    assert "password" not in body and "hashed_password" not in body


def test_registro_duplicado_da_409(client, make_user):
    make_user("ana@example.com")
    res = client.post(
        "/api/auth/register",
        json={"email": "ana@example.com", "name": "Otra", "password": PASSWORD},
    )
    assert res.status_code == 409


def test_contrasena_corta_da_422(client):
    res = client.post(
        "/api/auth/register", json={"email": "a@example.com", "name": "A", "password": "123"}
    )
    assert res.status_code == 422


def test_login_incorrecto_da_401(client, make_user):
    make_user("ana@example.com")
    res = client.post("/api/auth/login", data={"username": "ana@example.com", "password": "mala"})
    assert res.status_code == 401


def test_me_sin_token_da_401(client):
    assert client.get("/api/users/me").status_code == 401


def test_me_con_token_falso_da_401(client):
    res = client.get("/api/users/me", headers={"Authorization": "Bearer inventado"})
    assert res.status_code == 401


def test_me_y_editar_porcentaje_de_comida(client, auth):
    assert client.get("/api/users/me", headers=auth).json()["food_budget_pct"] == 30
    res = client.patch("/api/users/me", json={"food_budget_pct": 25}, headers=auth)
    assert res.status_code == 200
    assert res.json()["food_budget_pct"] == 25
