"""Tests de los endpoints de finanzas (de punta a punta, con la API)."""


def cargar_datos(client, auth):
    client.post("/api/incomes", json={"source": "Sueldo", "amount_cents": 6_000_000,
                                      "start_date": "2025-01-01"}, headers=auth)
    client.post("/api/expenses", json={"category": "housing", "kind": "fixed",
                                       "amount_cents": 1_500_000, "date": "2025-01-01"}, headers=auth)
    client.post("/api/subscriptions", json={"name": "Spotify", "amount_cents": 1_000}, headers=auth)
    client.post("/api/goals", json={"name": "Viaje", "target_cents": 3_000_000}, headers=auth)


def test_overview_trae_todo_el_dashboard(client, auth):
    cargar_datos(client, auth)
    res = client.get("/api/finance/overview", headers=auth)
    assert res.status_code == 200
    body = res.json()
    assert body["usd_rate"] == 40.0
    # 60.000 - 15.000 alquiler - 400 Spotify (US$ 10 x 40)
    assert body["capacity"]["disposable_income_cents"] == 4_460_000
    assert len(body["year"]["months"]) == 12
    assert body["food"]["percentage"] == 30
    assert body["goals"][0]["name"] == "Viaje"


def test_simular_con_monto(client, auth):
    cargar_datos(client, auth)
    res = client.post("/api/finance/simulate", json={"cost_cents": 200_000}, headers=auth)
    assert res.status_code == 200
    body = res.json()
    claves = [s["key"] for s in body["strategies"]]
    assert claves[:2] == ["cash", "save_first"] and "installments_12" in claves
    assert body["recommended_key"] == "cash"


def test_simular_compra_deseada_en_dolares(client, auth):
    cargar_datos(client, auth)
    item = client.post("/api/wishlist", json={"name": "Auriculares", "cost_cents": 15_000,
                                              "currency": "USD"}, headers=auth).json()
    res = client.post("/api/finance/simulate", json={"wish_item_id": item["id"]}, headers=auth)
    assert res.json()["price_cents"] == 600_000  # US$ 150 x 40


def test_simular_requiere_monto_o_item(client, auth):
    assert client.post("/api/finance/simulate", json={}, headers=auth).status_code == 422


def test_no_se_puede_simular_item_de_otro(client, make_user):
    ana = make_user("ana@example.com")
    beto = make_user("beto@example.com")
    item = client.post("/api/wishlist", json={"name": "Bici", "cost_cents": 100}, headers=ana).json()
    res = client.post("/api/finance/simulate", json={"wish_item_id": item["id"]}, headers=beto)
    assert res.status_code == 404
