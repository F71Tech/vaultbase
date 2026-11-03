"""cobros reales

Revision ID: b5c8e1f7a203
Revises: a91f3b6d2c40
Create Date: 2026-11-03 00:30:00

Lo que de verdad te entró cada día de cobro (manda sobre la estimación).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5c8e1f7a203'
down_revision: Union[str, Sequence[str], None] = 'a91f3b6d2c40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pay_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('income_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('kind', sa.Enum('pay', 'advance', name='paykind', native_enum=False, length=20), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['income_id'], ['incomes.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_pay_records_user_id'), 'pay_records', ['user_id'], unique=False)
    op.create_index(op.f('ix_pay_records_income_id'), 'pay_records', ['income_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pay_records_income_id'), table_name='pay_records')
    op.drop_index(op.f('ix_pay_records_user_id'), table_name='pay_records')
    op.drop_table('pay_records')
