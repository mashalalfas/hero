"""Test configuration — shared fixtures for all HERO tests."""

from __future__ import annotations

import pytest

from hero.state.sandbox import _cache


@pytest.fixture(autouse=True)
def clear_state_cache():
    """Reset the module-level ``_cache`` singleton before every test.

    ``_cache`` is keyed only on ``sandbox_name``, not ``base_path``, so
    stale entries from one test leak into the next when they share a name.
    This fixture guarantees a clean cache for each test.
    """
    _cache.invalidate()
