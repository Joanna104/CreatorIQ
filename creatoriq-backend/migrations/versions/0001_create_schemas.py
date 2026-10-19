"""Create the empty app, ds and synthetic schemas.

Revision ID: 0001
Revises:
Create Date: 2026-10-18

Phase 1: schemas only - no tables, no data. The schema comments record the rule that
synthetic data must never be used for model training or user-facing predictions.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Names are repeated here on purpose: a migration must stay frozen even if app code changes.
SCHEMAS = {
    "app": "CreatorIQ application data (users, profiles, predictions). Empty in Phase 1.",
    "ds": (
        "REAL observational datasets only. The only schema approved as a source for "
        "model training and predictions."
    ),
    "synthetic": (
        "SYNTHETIC DATA ONLY (test fixtures). Must never be used for model training "
        "or user-facing predictions."
    ),
}


def upgrade() -> None:
    for name, comment in SCHEMAS.items():
        op.execute(f'CREATE SCHEMA IF NOT EXISTS "{name}"')
        op.execute(f"COMMENT ON SCHEMA \"{name}\" IS '{comment}'")


def downgrade() -> None:
    # No CASCADE: if a schema has gained tables since, the downgrade fails instead of
    # silently destroying data.
    for name in reversed(list(SCHEMAS)):
        op.execute(f'DROP SCHEMA IF EXISTS "{name}"')
