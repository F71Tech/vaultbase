"""
Fábrica de endpoints CRUD (Crear, Leer, Actualizar, Borrar).

Ingresos, metas, suscripciones y compras deseadas necesitan exactamente los
mismos 5 endpoints. En vez de copiar y pegar el mismo código 4 veces
(principio DRY: "Don't Repeat Yourself"), esta función los genera para
cualquier modelo que le pasemos.

Regla de seguridad clave: cada consulta filtra por `user_id`, así un usuario
NUNCA puede ver ni tocar los datos de otro.
"""

from fastapi import APIRouter, HTTPException, Response, status
from sqlmodel import Session, select

from ..deps import CurrentUser, SessionDep


def build_crud_router(
    *,
    model,           # la tabla (ej: Goal)
    create_schema,   # lo que se recibe al crear (ej: GoalCreate)
    read_schema,     # lo que se devuelve (ej: GoalRead)
    update_schema,   # lo que se recibe al editar (ej: GoalUpdate)
    prefix: str,     # ruta base (ej: "/api/goals")
    tag: str,        # título del grupo en /docs
    order_by,        # orden del listado (ej: Goal.created_at)
    include_list: bool = True,
    # Validación extra después de editar, para reglas que dependen de varios
    # campos (ej: la subcategoría debe pertenecer a la categoría final).
    # Debe lanzar ValueError con un mensaje claro si algo no cuadra.
    validate_item=None,
    # Paso extra antes de guardar un registro nuevo (ej: completar la
    # cotización del dólar de un gasto en USD). Recibe (item, session).
    on_create=None,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])
    nombre = tag.lower()

    def get_owned(session: Session, user_id: int, item_id: int):
        """Busca un registro y verifica que sea del usuario; si no, 404."""
        item = session.get(model, item_id)
        if item is None or item.user_id != user_id:
            # Respondemos 404 (no 403) también cuando es de otro usuario:
            # así ni siquiera se revela que ese id existe.
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontrado")
        return item

    if include_list:
        @router.get("", response_model=list[read_schema], summary=f"Listar {nombre}")
        def list_items(session: SessionDep, user: CurrentUser):
            stmt = select(model).where(model.user_id == user.id).order_by(order_by)
            return session.exec(stmt).all()

    @router.post("", response_model=read_schema, status_code=status.HTTP_201_CREATED,
                 summary=f"Crear en {nombre}")
    def create_item(data: create_schema, session: SessionDep, user: CurrentUser):
        # El user_id sale del token, nunca de lo que manda el cliente
        item = model.model_validate(data, update={"user_id": user.id})
        if on_create:
            on_create(item, session)
        session.add(item)
        session.commit()
        session.refresh(item)
        return item

    @router.get("/{item_id}", response_model=read_schema, summary=f"Ver uno de {nombre}")
    def read_item(item_id: int, session: SessionDep, user: CurrentUser):
        return get_owned(session, user.id, item_id)

    @router.patch("/{item_id}", response_model=read_schema, summary=f"Editar en {nombre}")
    def update_item(item_id: int, data: update_schema, session: SessionDep, user: CurrentUser):
        item = get_owned(session, user.id, item_id)
        # exclude_unset: solo los campos que el cliente realmente envió
        item.sqlmodel_update(data.model_dump(exclude_unset=True))
        if validate_item:
            try:
                validate_item(item)
            except ValueError as error:
                # rollback deshace los cambios en memoria: el registro vuelve
                # a quedar exactamente como estaba en la base de datos
                session.rollback()
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error))
        session.add(item)
        session.commit()
        session.refresh(item)
        return item

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT,
                   summary=f"Borrar de {nombre}")
    def delete_item(item_id: int, session: SessionDep, user: CurrentUser):
        item = get_owned(session, user.id, item_id)
        session.delete(item)
        session.commit()
        # 204 No Content: salió bien y no hay nada que devolver
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
