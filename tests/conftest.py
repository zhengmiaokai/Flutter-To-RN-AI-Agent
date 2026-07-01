"""tests/conftest — Shared test fixtures for the Flutter-to-RN converter."""

import tempfile
from pathlib import Path

import pytest

from framework.config import Config


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test output."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def sample_config(temp_dir):
    """Create a Config instance pointing to a temp directory."""
    return Config(
        source_dir=".",
        target_dir=str(temp_dir),
        model="deepseek-v4-pro",
        api_key="test-key",
        skip_setup=True,
        skip_conversion=True,
        skip_verification=True,
    )