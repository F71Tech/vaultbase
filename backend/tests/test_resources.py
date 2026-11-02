"""Tests del CRUD de ingresos, gastos, metas, suscripciones y compras deseadas."""


def test_crear_y_listar_ingreso(client, auth):
    res = client.post(
        "/api/incomes",
        json={"source": "Sueldo", "amount_cents": 6500000, "frequency": "monthly"},
        headers=auth,
    )
    assert res.status_code == 201
    assert res.json()["currency"] == "UYU"  # moneda por defecto
    lista = client.get("/api/incomes", headers=auth).json()
    assert len(lista) == 1 and lista[0]["source"] == "Sueldo"


def test_monto_negativo_da_422(client, auth):
    res = client.post(
        "/api/expenses", json={"category": "food", "amount_cents": -100}, headers=auth
    )
    assert res.status_code == 422


def test_filtrar_gastos_por_fecha_y_categoria(client, auth):
    gastos = [
        {"category": "food", "amount_cents": 50000, "date": "2026-10-05"},
        {"category": "food", "amount_cents": 30000, "date": "2026-11-01"},
        {"category": "transport", "amount_cents": 8000, "date": "2026-11-02"},
    ]
    for g in gastos:
        client.post("/api/expenses", json=g, headers=auth)

    noviembre = client.get(
        "/api/expenses?from_date=2026-11-01&to_date=2026-11-30", headers=auth
    ).json()
    assert len(noviembre) == 2
    assert noviembre[0]["date"] == "2026-11-02"  # más nuevo primero

    comida = client.get("/api/expenses?category=food", headers=auth).json()
    assert {g["amount_cents"] for g in comida} == {50000, 30000}


def test_editar_meta_parcialmente(client, auth):
    meta = client.post(
        "/api/goals",
        json={"name": "Viaje", "target_cents": 10000000, "deadline": "2027-06-01"},
        headers=auth,
    ).json()
    res = client.patch(f"/api/goals/{meta['id']}", json={"saved_cents": 250000}, headers=auth)
    assert res.json()["saved_cents"] == 250000
    assert res.json()["name"] == "Viaje"  # lo que no se envió, no cambia

    # La fecha límite es opcional: se puede quitar enviando null
    res = client.patch(f"/api/goals/{meta['id']}", json={"deadline": None}, headers=auth)
    assert res.json()["deadline"] is None


def test_no_se_puede_vaciar_un_campo_obligatorio(client, auth):
    meta = client.post(
        "/api/goals", json={"name": "Auto", "target_cents": 100}, headers=auth
    ).json()
    res = client.patch(f"/api/goals/{meta['id']}", json={"name": None}, headers=auth)
    assert res.status_code == 422


def test_un_usuario_no_ve_datos_de_otro(client, make_user):
    ana = make_user("ana@example.com")
    beto = make_user("beto@example.com")
    meta = client.post(
        "/api/goals", json={"name": "Secreta", "target_cents": 100}, headers=ana
    ).json()

    assert client.get("/api/goals", headers=beto).json() == []
    assert client.get(f"/api/goals/{meta['id']}", headers=beto).status_code == 404
    assert client.delete(f"/api/goals/{meta['id']}", headers=beto).status_code == 404
    # Y la meta sigue existiendo para Ana
    assert client.get(f"/api/goals/{meta['id']}", headers=ana).status_code == 200


def test_suscripcion_en_dolares_y_borrar(client, auth):
    sub = client.post(
        "/api/subscriptions",
        json={"name": "Spotify", "amount_cents": 1199, "billing_day": 15},
        headers=auth,
    ).json()
    assert sub["currency"] == "USD"  # por defecto, las suscripciones son en dólares
    assert client.delete(f"/api/subscriptions/{sub['id']}", headers=auth).status_code == 204
    assert client.get("/api/subscriptions", headers=auth).json() == []


def test_compra_deseada(client, auth):
    res = client.post(
        "/api/wishlist",
        json={"name": "Notebook", "cost_cents": 4500000, "priority": "high"},
        headers=auth,
    )
    assert res.status_code == 201 and res.json()["priority"] == "high"


def test_endpoints_requieren_login(client):
    for ruta in ["/api/incomes", "/api/expenses", "/api/goals", "/api/subscriptions", "/api/wishlist"]:
        assert client.get(ruta).status_code == 401
