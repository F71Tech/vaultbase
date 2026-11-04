"""Tests de la cuenta demo y de borrar la cuenta."""

import datetime as dt

from sqlmodel import select

from backend.app.models import Expense, User
from backend.app.services import demo


def test_demo_crea_cuenta_con_datos_y_entra(client):
    res = client.post("/api/auth/demo")
    assert res.status_code == 200
    h = {"Authorization": f"Bearer {res.json()['access_token']}"}
    me = client.get("/api/users/me", headers=h).json()
    assert demo.is_demo_email(me["email"])
    assert me["name"] in demo.DEMO_NAMES
    assert me["tour_done"] is False                          # la guía le sale al entrar
    ov =client.get("/api/finance/overview", headers=h).json()
    assert ov["capacity"]["monthly_savings_cents"] > 0      # la demo tiene una economía sana
    assert len(ov["goals"]) == 3
    assert ov["year"]["months"][11]["aguinaldo_cents"] > 0   # el sueldo trae aguinaldo
    assert len(client.get("/api/subscriptions", headers=h).json()) == 5


def test_cada_demo_es_una_cuenta_distinta(client):
    a = client.post("/api/auth/demo").json()["access_token"]
    b = client.post("/api/auth/demo").json()["access_token"]
    me_a = client.get("/api/users/me", headers={"Authorization": f"Bearer {a}"}).json()
    me_b = client.get("/api/users/me", headers={"Authorization": f"Bearer {b}"}).json()
    assert me_a["id"] != me_b["id"]


def test_los_archivos_de_la_app_se_revalidan(client):
    # Para que nadie se quede con una versión vieja después de publicar un cambio
    assert client.get("/js/tour.js").headers["cache-control"] == "no-cache"


def test_las_demos_viejas_se_borran(session):
    user = demo.create_demo_user(session)
    user.created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=demo.DEMO_TTL_HOURS + 1)
    session.add(user)
    session.commit()
    assert demo.cleanup_old_demos(session) == 1
    assert session.exec(select(User)).all() == []
    assert session.exec(select(Expense)).all() == []  # sus datos también


def test_borrar_mi_cuenta(client, auth, session):
    client.post("/api/expenses", json={"category": "food", "amount_cents": 100}, headers=auth)
    assert client.delete("/api/users/me", headers=auth).status_code == 204
    assert session.exec(select(Expense)).all() == []
    # El token ya no sirve: el usuario no existe
    assert client.get("/api/users/me", headers=auth).status_code == 401
