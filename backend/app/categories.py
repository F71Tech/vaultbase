"""
Árbol de categorías de gastos: categoría principal -> subcategorías.

Es la ÚNICA fuente de verdad: el backend lo usa para validar y el frontend
lo pide a /api/categories para armar los botones (con su nombre en español
y su ícono). Si querés agregar una subcategoría, se agrega solo acá.

- key (ej: "groceries"): identificador técnico que se guarda en la base.
- label: el nombre que ve el usuario.
- icon: nombre del ícono (set "Lucide", que usaremos en el frontend).
"""

CATEGORY_TREE: dict[str, dict] = {
    "food": {
        "label": "Comida",
        "icon": "utensils",
        "subcategories": {
            "groceries": "Supermercado",
            "market": "Feria y almacén",
            "eating_out": "Restaurantes y bares",
            "delivery": "Delivery",
            "snacks": "Kiosco y antojos",
        },
    },
    "transport": {
        "label": "Transporte",
        "icon": "bus",
        "subcategories": {
            "bus": "Ómnibus (STM)",
            "taxi_apps": "Taxi y apps",
            "fuel": "Combustible",
            "parking_tolls": "Estacionamiento y peajes",
            "vehicle_maintenance": "Mantenimiento del vehículo",
        },
    },
    "housing": {
        "label": "Vivienda",
        "icon": "house",
        "subcategories": {
            "rent": "Alquiler",
            "common_fees": "Gastos comunes",
            "home_repairs": "Arreglos del hogar",
            "furniture": "Muebles y deco",
        },
    },
    "utilities": {
        "label": "Servicios",
        "icon": "plug",
        "subcategories": {
            "electricity": "Luz (UTE)",
            "water": "Agua (OSE)",
            "internet_phone": "Internet y teléfono",
            "gas": "Gas",
        },
    },
    "health": {
        "label": "Salud",
        "icon": "heart-pulse",
        "subcategories": {
            "health_plan": "Mutualista y emergencia",
            "pharmacy": "Farmacia",
            "doctor": "Consultas y estudios",
            "gym": "Gimnasio y deporte",
        },
    },
    "personal_care": {
        "label": "Cuidado personal",
        "icon": "sparkles",
        "subcategories": {
            "hairdresser": "Peluquería y barbería",
            "cosmetics": "Higiene y cosmética",
        },
    },
    "education": {
        "label": "Educación",
        "icon": "graduation-cap",
        "subcategories": {
            "tuition": "Matrícula y cuotas",
            "courses": "Cursos",
            "books": "Libros y materiales",
        },
    },
    "leisure": {
        "label": "Ocio",
        "icon": "party-popper",
        "subcategories": {
            "outings": "Salidas",
            "events": "Eventos y entradas",
            "travel": "Viajes",
            "hobbies": "Hobbies y juegos",
        },
    },
    "clothing": {
        "label": "Ropa",
        "icon": "shirt",
        "subcategories": {
            "clothes": "Ropa",
            "shoes": "Calzado",
            "fashion_accessories": "Accesorios",
        },
    },
    "tech": {
        "label": "Tecnología",
        "icon": "smartphone",
        "subcategories": {
            "devices": "Dispositivos",
            "tech_accessories": "Accesorios",
            "software": "Software y apps",
        },
    },
    "pets": {
        "label": "Mascotas",
        "icon": "paw-print",
        "subcategories": {
            "pet_food": "Alimento",
            "vet": "Veterinaria",
            "pet_supplies": "Accesorios y cuidado",
        },
    },
    "gifts": {
        "label": "Regalos y donaciones",
        "icon": "gift",
        "subcategories": {
            "presents": "Regalos",
            "donations": "Donaciones",
        },
    },
    "finance": {
        "label": "Bancos e impuestos",
        "icon": "landmark",
        "subcategories": {
            "bank_fees": "Comisiones bancarias",
            "card_interest": "Intereses de tarjeta",
            "taxes": "Impuestos y tributos",
        },
    },
    "other": {
        "label": "Otros",
        "icon": "ellipsis",
        "subcategories": {},
    },
}


def is_valid_subcategory(category: str, subcategory: str | None) -> bool:
    """Una subcategoría es válida si está vacía o pertenece a esa categoría."""
    if subcategory is None:
        return True  # sin subcategoría = "general" dentro de la categoría
    key = getattr(category, "value", category)  # acepta el Enum o el texto
    return subcategory in CATEGORY_TREE[key]["subcategories"]
