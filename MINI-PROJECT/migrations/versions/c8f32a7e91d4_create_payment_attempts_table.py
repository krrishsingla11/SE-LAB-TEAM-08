"""create payment_attempts table and uq_payments_transaction_ref

Revision ID: c8f32a7e91d4
Revises: 4077070e99a9
Create Date: 2026-11-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8f32a7e91d4'
down_revision: Union[str, Sequence[str], None] = '4077070e99a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Pre-check for duplicate transaction_refs before applying unique constraint
    conn = op.get_bind()
    dupes_query = sa.text(
        "SELECT transaction_ref, COUNT(*) as cnt FROM payments "
        "WHERE transaction_ref IS NOT NULL GROUP BY transaction_ref HAVING COUNT(*) > 1"
    )
    duplicates = conn.execute(dupes_query).fetchall()
    if duplicates:
        dupe_refs = [f"{row[0]} ({row[1]} times)" for row in duplicates]
        raise RuntimeError(
            f"Cannot apply unique constraint uq_payments_transaction_ref: "
            f"Found duplicate transaction_refs in payments table: {', '.join(dupe_refs)}. "
            f"Manual deduplication required."
        )

    # 2. Add unique constraint to payments.transaction_ref
    op.create_unique_constraint('uq_payments_transaction_ref', 'payments', ['transaction_ref'])

    # 3. Create payment_attempts table with non-redundant uniqueness
    op.create_table(
        'payment_attempts',
        sa.Column('attempt_id', sa.Integer(), nullable=False),
        sa.Column('buyer_id', sa.Integer(), nullable=False),
        sa.Column('cart_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='INR'),
        sa.Column('cart_hash', sa.String(length=64), nullable=False),
        sa.Column('razorpay_order_id', sa.String(length=100), nullable=False),
        sa.Column('razorpay_payment_id', sa.String(length=100), nullable=True),
        sa.Column(
            'status',
            sa.Enum(
                'created',
                'callback_received',
                'completed',
                'refund_pending',
                'refunded',
                'refund_failed',
                'partial_refunded',
                'manual_review',
                name='payment_attempt_status',
            ),
            nullable=False,
            server_default='created',
        ),
        sa.Column('refund_idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('refund_ref', sa.String(length=100), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('unrefunded_amount', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['buyer_id'], ['users.user_id']),
        sa.ForeignKeyConstraint(['cart_id'], ['carts.cart_id']),
        sa.PrimaryKeyConstraint('attempt_id'),
        sa.UniqueConstraint('razorpay_order_id', name='uq_payment_attempts_razorpay_order_id'),
        sa.UniqueConstraint(
            'refund_idempotency_key',
            name='uq_payment_attempts_refund_idempotency_key'
        ),
    )
    op.create_index(
        op.f('ix_payment_attempts_buyer_id'), 'payment_attempts', ['buyer_id'], unique=False
    )
    op.create_index(
        op.f('ix_payment_attempts_cart_id'), 'payment_attempts', ['cart_id'], unique=False
    )
    op.create_index(
        op.f('ix_payment_attempts_razorpay_payment_id'),
        'payment_attempts',
        ['razorpay_payment_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_payment_attempts_status'), 'payment_attempts', ['status'], unique=False
    )
    op.create_index(
        'ix_payment_attempts_cart_hash_status',
        'payment_attempts',
        ['cart_id', 'cart_hash', 'status'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_payment_attempts_cart_hash_status', table_name='payment_attempts')
    op.drop_index(op.f('ix_payment_attempts_status'), table_name='payment_attempts')
    op.drop_index(op.f('ix_payment_attempts_razorpay_payment_id'), table_name='payment_attempts')
    op.drop_index(op.f('ix_payment_attempts_cart_id'), table_name='payment_attempts')
    op.drop_index(op.f('ix_payment_attempts_buyer_id'), table_name='payment_attempts')
    op.drop_table('payment_attempts')
    with op.batch_alter_table('payments') as batch_op:
        batch_op.drop_constraint('uq_payments_transaction_ref', type_='unique')
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        sa.Enum(name='payment_attempt_status').drop(bind, checkfirst=True)
