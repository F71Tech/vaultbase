"""quitar saldo manual

Revision ID: c3d81f0e2b6a
Revises: 5a9a9aab3fb7
Create Date: 2026-11-02 20:40:00

"Tu plata hoy" ahora se calcula sola con los movimientos del mes: ya no hace
falta que el usuario cargue su saldo, así que borramos esas dos columnas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d81f0e2b6a'
down_revision: Union[str, Sequence[str], None] = '5a9a9aab3fb7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_column('balance_at')
        batch.drop_column('balance_cents')


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('balance_cents', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('balance_at', sa.DateTime(), nullable=True))
