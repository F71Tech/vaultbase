"""Catálogo de categorías y subcategorías de gastos (público, no requiere login)."""

from fastapi import APIRouter
from pydantic import BaseModel

from ..categories import CATEGORY_TREE

router = APIRouter(prefix="/api/categories", tags=["Categorías"])


class SubcategoryOut(BaseModel):
    key: str
    label: str


class CategoryOut(BaseModel):
    key: str
    label: str
    icon: str
    subcategories: list[SubcategoryOut]


@router.get("", response_model=list[CategoryOut])
def list_categories():
    """Devuelve el árbol de categorías para armar los selectores del frontend."""
    return [
        CategoryOut(
            key=key,
            label=data["label"],
            icon=data["icon"],
            subcategories=[
                SubcategoryOut(key=sub_key, label=sub_label)
                for sub_key, sub_label in data["subcategories"].items()
            ],
        )
        for key, data in CATEGORY_TREE.items()
    ]
