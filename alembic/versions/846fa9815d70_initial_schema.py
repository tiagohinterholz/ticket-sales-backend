"""initial schema

Revision ID: 846fa9815d70
Revises:
Create Date: 2026-08-12 22:57:03.647991

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '846fa9815d70'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: manually reordered from the raw autogenerate output — Alembic could
    # not topologically sort `seats`/`tickets` (SAWarning: unresolvable cycle)
    # because seats.current_ticket_id -> tickets.id and tickets.seat_id ->
    # seats.id reference each other. Tables are created in real dependency
    # order below; the seats.current_ticket_id FK is added separately via
    # `create_foreign_key` once `tickets` exists, breaking the cycle.
    op.create_table('users',
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('password_hash', sa.String(), nullable=False),
    sa.Column('role', sa.Enum('CUSTOMER', 'ORGANIZER', 'GATE_STAFF', name='role'), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('events',
    sa.Column('organizer_id', sa.Uuid(), nullable=False),
    sa.Column('tmdb_movie_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('poster_url', sa.String(), nullable=True),
    sa.Column('venue', sa.String(), nullable=False),
    sa.Column('starts_at', sa.DateTime(), nullable=False),
    sa.Column('rows', sa.Integer(), nullable=False),
    sa.Column('seats_per_row', sa.Integer(), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=False),
    sa.Column('price_cents', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('PUBLISHED', 'CANCELLED', name='event_status'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organizer_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('seats',
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('row_label', sa.String(), nullable=False),
    sa.Column('seat_number', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('AVAILABLE', 'HOLD', 'SOLD', name='seat_status'), nullable=False),
    sa.Column('current_ticket_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('event_id', 'row_label', 'seat_number', name='uq_seat_event_row_number')
    )
    op.create_table('tickets',
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('seat_id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.Enum('HELD', 'PAID', 'USED', 'CANCELLED', 'EXPIRED', 'TRANSFERRED', name='ticket_status'), nullable=False),
    sa.Column('qr_secret', sa.String(), nullable=False),
    sa.Column('held_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('paid_at', sa.DateTime(), nullable=True),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['seat_id'], ['seats.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_foreign_key('fk_seats_current_ticket_id_tickets', 'seats', 'tickets', ['current_ticket_id'], ['id'])
    op.create_table('payment_attempts',
    sa.Column('ticket_id', sa.Uuid(), nullable=False),
    sa.Column('card_last4', sa.String(), nullable=False),
    sa.Column('result', sa.Enum('APPROVED', 'DECLINED', name='payment_result'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('transfer_invites',
    sa.Column('ticket_id', sa.Uuid(), nullable=False),
    sa.Column('from_user_id', sa.Uuid(), nullable=False),
    sa.Column('to_email', sa.String(), nullable=False),
    sa.Column('to_user_id', sa.Uuid(), nullable=True),
    sa.Column('token', sa.String(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'ACCEPTED', 'DECLINED', 'CANCELLED', 'EXPIRED', name='transfer_invite_status'), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['from_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
    sa.ForeignKeyConstraint(['to_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token')
    )
    op.create_table('fake_email_log',
    sa.Column('to_email', sa.String(), nullable=False),
    sa.Column('subject', sa.String(), nullable=False),
    sa.Column('body', sa.String(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('fake_email_log')
    op.drop_table('transfer_invites')
    op.drop_table('payment_attempts')
    op.drop_constraint('fk_seats_current_ticket_id_tickets', 'seats', type_='foreignkey')
    op.drop_table('tickets')
    op.drop_table('seats')
    op.drop_table('events')
    op.drop_table('users')
    # NOTE: `op.drop_table` does not drop the Postgres ENUM types backing
    # `sa.Enum` columns (they are only dropped implicitly when using
    # `Enum.drop()`/`metadata.drop_all`, not raw `op.drop_table`). Without
    # this, re-running `upgrade` after a `downgrade` fails with
    # "type already exists" — dropped explicitly here so downgrade is truly
    # reversible.
    sa.Enum(name='transfer_invite_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='payment_result').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='ticket_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='seat_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='event_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='role').drop(op.get_bind(), checkfirst=True)
