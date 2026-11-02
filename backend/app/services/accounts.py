"""Operaciones sobre cuentas completas: borrar un usuario con todos sus datos."""

from sqlmodel import Session, delete

from ..models import Expense, Goal, Income, Subscription, User, WishItem

# Tablas que pertenecen a un usuario (columna user_id)
USER_TABLES = (Income, Expense, Subscription, Goal, WishItem)


def delete_user_data(session: Session, user_id: int) -> None:
    """
    Borra al usuario y TODO lo que cargó. Primero los datos y después el
    usuario: si fuera al revés, quedarían filas "huérfanas" apuntando a un
    usuario que ya no existe (la base de datos lo impediría con la foreign key).
    """
    for model in USER_TABLES:
        session.exec(delete(model).where(model.user_id == user_id))
    session.exec(delete(User).where(User.id == user_id))
    session.commit()
