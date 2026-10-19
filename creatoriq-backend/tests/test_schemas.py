"""The real-vs-synthetic data rule, and 'no models yet' in Phase 1."""

import pytest

from app.db.base import Base
from app.db.schemas import (
    ALL_SCHEMAS,
    APP_SCHEMA,
    MODEL_TRAINING_SCHEMAS,
    REAL_DATA_SCHEMA,
    SYNTHETIC_SCHEMA,
    ForbiddenDataSourceError,
    ensure_training_allowed,
)


def test_schema_names():
    assert ALL_SCHEMAS == ("app", "ds", "synthetic")
    assert (APP_SCHEMA, REAL_DATA_SCHEMA, SYNTHETIC_SCHEMA) == ("app", "ds", "synthetic")


def test_only_the_real_data_schema_is_approved_for_training():
    assert MODEL_TRAINING_SCHEMAS == frozenset({"ds"})
    ensure_training_allowed("ds")
    ensure_training_allowed(" DS ")  # tolerant of case/whitespace


def test_synthetic_schema_is_rejected_for_training_with_a_clear_message():
    for spelling in ("synthetic", "SYNTHETIC", " synthetic "):
        with pytest.raises(ForbiddenDataSourceError, match="synthetic data"):
            ensure_training_allowed(spelling)


@pytest.mark.parametrize("schema", ["app", "public", "", "ds_backup", "synthetic.viral_video"])
def test_every_other_schema_is_rejected_too(schema):
    with pytest.raises(ForbiddenDataSourceError):
        ensure_training_allowed(schema)


def test_no_tables_are_defined_yet():
    assert Base.metadata.tables == {}
