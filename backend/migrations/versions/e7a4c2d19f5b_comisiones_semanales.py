"""comisiones semanales

Revision ID: e7a4c2d19f5b
Revises: c3d81f0e2b6a
Create Date: 2026-11-02 22:10:00

Sueldos con parte variable: tabla de comisiones por semana (con rango
mínimo-máximo y monto real) y el bono mínimo semanal en el ingreso.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a4c2d19f5b'
down_revision: Union[str, Sequence[str], None] = 'c3d81f0e2b6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'commissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('week_start', sa.Date(), nullable=False),
        sa.Column('min_cents', sa.Integer(), nullable=False),
        sa.Column('max_cents', sa.Integer(), nullable=False),
        sa.Column('actual_cents', sa.Integer(), nullable=True),
        sa.Column('note', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_commissions_user_id'), 'commissions', ['user_id'], unique=False)
    with op.batch_alter_table('incomes') as batch:
        batch.add_column(sa.Column('commission_floor_cents', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('incomes') as batch:
        batch.drop_column('commission_floor_cents')
    op.drop_index(op.f('ix_commissions_user_id'), table_name='commissions')
    op.drop_table('commissions')
