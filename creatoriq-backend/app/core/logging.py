"""Minimal logging setup."""

import logging


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # basicConfig is a no-op when handlers already exist (e.g. under pytest/uvicorn),
    # so set the level explicitly as well.
    logging.getLogger().setLevel(level)
