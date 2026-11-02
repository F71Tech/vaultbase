"""saldo actual, dia de cobro y adelanto

Revision ID: 5a9a9aab3fb7
Revises: 7b329ca03f30
Create Date: 2026-11-02 19:18:01.208111

Escrita a mano (no autogenerada): el autogenerate también "veía" cambios en
los enums que solo eran diferencias de largo del texto en la base local.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a9a9aab3fb7'
down_revision: Union[str, Sequence[str], None] = '7b329ca03f30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch_alter_table: SQLite no sabe modificar tablas "en el lugar";
    # Alembic copia la tabla por detrás. En PostgreSQL es un ALTER TABLE normal.
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('balance_cents', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('balance_at', sa.DateTime(), nullable=True))
    with op.batch_alter_table('incomes') as batch:
        # server_default: los ingresos que ya existen quedan con "se cobra el día 1"
        batch.add_column(sa.Column('pay_day', sa.Integer(), nullable=False, server_default='1'))
        batch.add_column(sa.Column('advance_cents', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('advance_day', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('incomes') as batch:
        batch.drop_column('advance_day')
        batch.drop_column('advance_cents')
        batch.drop_column('pay_day')
    with op.batch_alter_table('users') as batch:
        batch.drop_column('balance_at')
        batch.drop_column('balance_cents')
