"""Shared pytest fixtures for the RetroIPTVGuide test suite."""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def isolated_epg_cache(tmp_path):
    """Redirect EPG_CACHE_DIR to a temporary directory for every test.

    This prevents EPG cache files produced during one test from being picked
    up by a later test that does not expect a pre-populated cache.
    """
    import app as app_module

    orig = app_module.EPG_CACHE_DIR
    app_module.EPG_CACHE_DIR = str(tmp_path / "epg_cache")
    yield
    app_module.EPG_CACHE_DIR = orig
