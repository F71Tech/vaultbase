"""ticket de alimentacion

Revision ID: a91f3b6d2c40
Revises: e7a4c2d19f5b
Create Date: 2026-11-02 23:30:00

Ingresos "solo para comida" (ticket de alimentación): no son plata libre.
Y en cada gasto, si se pagó con el ticket o con plata propia.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a91f3b6d2c40'
down_revision: Union[str, Sequence[str], None] = 'e7a4c2d19f5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('incomes') as batch:
        # server_default: los ingresos que ya existen quedan como plata normal
        batch.add_column(sa.Column('food_only', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('expenses') as batch:
        # True = lo pagué con el ticket, False = con mi plata, NULL = automático
        batch.add_column(sa.Column('paid_with_ticket', sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('expenses') as batch:
        batch.drop_column('paid_with_ticket')
    with op.batch_alter_table('incomes') as batch:
        batch.drop_column('food_only')
