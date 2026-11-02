"""Tests de categorías y subcategorías de gastos."""

from backend.app.categories import CATEGORY_TREE
from backend.app.models import ExpenseCategory


def test_enum_y_arbol_coinciden():
    # Si alguien agrega una categoría en un lado y se olvida del otro, esto falla
    assert {c.value for c in ExpenseCategory} == set(CATEGORY_TREE)


def test_catalogo_publico(client):
    res = client.get("/api/categories")
    assert res.status_code == 200
    comida = next(c for c in res.json() if c["key"] == "food")
    assert comida["label"] == "Comida"
    assert {"key": "snacks", "label": "Kiosco y antojos"} in comida["subcategories"]


def test_gasto_diario_con_subcategoria(client, auth):
    res = client.post(
        "/api/expenses",
        json={"category": "food", "subcategory": "snacks", "amount_cents": 6000,
              "description": "Alfajor"},
        headers=auth,
    )
    assert res.status_code == 201
    assert res.json()["kind"] == "variable"  # por defecto, gasto del día a día
    antojos = client.get("/api/expenses?subcategory=snacks", headers=auth).json()
    assert len(antojos) == 1


def test_subcategoria_de_otra_categoria_da_422(client, auth):
    res = client.post(
        "/api/expenses",
        json={"category": "transport", "subcategory": "snacks", "amount_cents": 6000},
        headers=auth,
    )
    assert res.status_code == 422


def test_cambiar_categoria_sin_ajustar_subcategoria_da_422(client, auth):
    gasto = client.post(
        "/api/expenses",
        json={"category": "food", "subcategory": "delivery", "amount_cents": 45000},
        headers=auth,
    ).json()
    url = f"/api/expenses/{gasto['id']}"

    assert client.patch(url, json={"category": "leisure"}, headers=auth).status_code == 422
    # El gasto no cambió
    assert client.get(url, headers=auth).json()["category"] == "food"
    # Cambiando ambas cosas juntas, sí funciona
    res = client.patch(url, json={"category": "leisure", "subcategory": "outings"}, headers=auth)
    assert res.status_code == 200 and res.json()["subcategory"] == "outings"
