"""keep push log history when subscriptions are pruned

Dead subscriptions are pruned on 404 and 410, but the original cascade
deleted their send history along with them. Web push has no delivery
receipts, so that history is the only evidence a send was attempted.
The foreign key now sets null instead, and the endpoint is copied onto
each log row so the target stays readable after pruning.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-07 00:13:48.813299

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("push_log", sa.Column("endpoint", sa.Text(), server_default="", nullable=False))
    op.alter_column("push_log", "subscription_id", existing_type=sa.INTEGER(), nullable=True)
    op.drop_constraint(
        op.f("fk_push_log_subscription_id_push_subscriptions"), "push_log", type_="foreignkey"
    )
    op.create_foreign_key(
        op.f("fk_push_log_subscription_id_push_subscriptions"),
        "push_log",
        "push_subscriptions",
        ["subscription_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Reverse the change.

    Log rows whose subscription was pruned carry a null subscription_id and
    cannot be represented under the old schema; they are deleted so the not
    null constraint can be restored.
    """
    op.execute("DELETE FROM push_log WHERE subscription_id IS NULL")
    op.drop_constraint(
        op.f("fk_push_log_subscription_id_push_subscriptions"), "push_log", type_="foreignkey"
    )
    op.create_foreign_key(
        op.f("fk_push_log_subscription_id_push_subscriptions"),
        "push_log",
        "push_subscriptions",
        ["subscription_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("push_log", "subscription_id", existing_type=sa.INTEGER(), nullable=False)
    op.drop_column("push_log", "endpoint")
