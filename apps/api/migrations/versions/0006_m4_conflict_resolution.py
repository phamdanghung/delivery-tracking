"""Retain acknowledged conflict decisions and replacement links (DEC-036)."""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE driver_conflict_resolutions (
      actor_user_id uuid NOT NULL,
      client_action_id uuid NOT NULL,
      resolution_hash text NOT NULL,
      command_json jsonb NOT NULL,
      review_snapshot jsonb NOT NULL,
      reason text NOT NULL,
      decided_at timestamptz NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      replacement_client_action_id uuid,
      PRIMARY KEY(actor_user_id,client_action_id),
      FOREIGN KEY(actor_user_id,client_action_id)
        REFERENCES driver_action_receipts(actor_user_id,client_action_id)
    )""")


def downgrade() -> None:
    op.drop_table("driver_conflict_resolutions")
