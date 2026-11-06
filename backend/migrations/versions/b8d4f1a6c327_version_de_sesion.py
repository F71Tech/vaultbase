"""version de sesion

Revision ID: b8d4f1a6c327
Revises: a7c3e9d1f420
Create Date: 2026-11-06 21:00:00

Cada cuenta tiene una "versión de sesión" que sube al cambiar la contraseña:
las sesiones creadas con un número anterior dejan de valer.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d4f1a6c327'
down_revision: Union[str, Sequence[str], None] = 'a7c3e9d1f420'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_column('token_version')
