"""Operaciones sobre cuentas completas: borrar un usuario con todos sus datos."""

from sqlmodel import Session, delete

from ..models import (
    Commission, Expense, Feedback, Goal, Income, PasswordReset, PayRecord, Subscription, User, WishItem,
)

# Tablas que pertenecen a un usuario (columna user_id).
# PayRecord va ANTES que Income: apunta a un ingreso (foreign key) y si no, la base no deja borrarlo.
USER_TABLES = (PayRecord, Income, Expense, Subscription, Goal, WishItem, Commission, PasswordReset, Feedback)


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
