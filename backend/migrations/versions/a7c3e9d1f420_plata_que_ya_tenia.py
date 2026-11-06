"""plata que ya tenia

Revision ID: a7c3e9d1f420
Revises: f4b7e2a9c816
Create Date: 2026-11-06 12:00:00

Marca los ingresos que en realidad son plata que la persona ya tenía: suman a
"Tu plata hoy", pero no cuentan como ingreso del mes. Los que ya se habían
cargado con el botón "Sumala una vez" pasan a estar marcados.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3e9d1f420'
down_revision: Union[str, Sequence[str], None] = 'f4b7e2a9c816'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('incomes') as batch:
        batch.add_column(sa.Column('previous_money', sa.Boolean(), nullable=False, server_default=sa.false()))
    incomes = sa.table('incomes', sa.column('previous_money', sa.Boolean()),
                       sa.column('source', sa.String()), sa.column('frequency', sa.String()))
    op.execute(incomes.update()
               .where(incomes.c.source == 'Plata que ya tenía', incomes.c.frequency == 'one_time')
               .values(previous_money=True))


def downgrade() -> None:
    with op.batch_alter_table('incomes') as batch:
        batch.drop_column('previous_money')
