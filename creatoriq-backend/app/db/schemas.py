"""PostgreSQL schema names and the real-vs-synthetic data rule.

Three schemas exist, created empty by the first migration:

* ``app``       - CreatorIQ's own application data.
* ``ds``        - REAL observational datasets only.
* ``synthetic`` - synthetic data (test fixtures only).

RULE: synthetic data must never be used to train a model or to produce a user-facing
prediction. Any future training or prediction code must call
``ensure_training_allowed(schema)`` for every schema it reads from; only ``ds`` passes.
"""

from __future__ import annotations

APP_SCHEMA = "app"
REAL_DATA_SCHEMA = "ds"
SYNTHETIC_SCHEMA = "synthetic"

ALL_SCHEMAS: tuple[str, ...] = (APP_SCHEMA, REAL_DATA_SCHEMA, SYNTHETIC_SCHEMA)

# The only schemas that may feed model training / predictions.
MODEL_TRAINING_SCHEMAS: frozenset[str] = frozenset({REAL_DATA_SCHEMA})


class ForbiddenDataSourceError(RuntimeError):
    """Raised when code tries to use a non-approved schema as a training/prediction source."""


def ensure_training_allowed(schema: str) -> None:
    """Raise unless ``schema`` is an approved real-data source for training/predictions."""
    name = schema.strip().lower()
    if name in MODEL_TRAINING_SCHEMAS:
        return
    if name == SYNTHETIC_SCHEMA:
        raise ForbiddenDataSourceError(
            "Schema 'synthetic' contains synthetic data and must never be used for model "
            "training or user-facing predictions."
        )
    raise ForbiddenDataSourceError(
        f"Schema {schema!r} is not an approved model-training source "
        f"(allowed: {sorted(MODEL_TRAINING_SCHEMAS)})."
    )
