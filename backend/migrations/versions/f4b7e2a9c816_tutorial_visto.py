"""tutorial visto

Revision ID: f4b7e2a9c816
Revises: d2f6a8c4e911
Create Date: 2026-11-03 12:00:00

Guardamos en la CUENTA si ya vio el tutorial (antes era solo en el navegador,
y en el iPhone la app instalada tiene su propia memoria: volvía a salir).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4b7e2a9c816'
down_revision: Union[str, Sequence[str], None] = 'd2f6a8c4e911'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        # server_default true: las cuentas que ya existen NO lo vuelven a ver.
        # Las nuevas se crean con False desde el modelo.
        batch.add_column(sa.Column('tour_done', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_column('tour_done')
