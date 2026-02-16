# tests/test_epg_cache.py
# Tests for EPG cache functionality

import pytest
import sys
import os
from datetime import datetime, timezone, timedelta

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_cache_duration_default():
    """Test that default cache duration is 1800 seconds (30 minutes)"""
    from app import get_cache_duration
    duration = get_cache_duration()
    assert duration == 1800, f"Expected default cache duration to be 1800, got {duration}"

def test_cache_info_structure():
    """Test that get_cache_info returns the expected structure"""
    from app import get_cache_info
    cache_info = get_cache_info()
    
    # Check that all expected keys are present
    expected_keys = ['cached_at', 'expires_at', 'age_seconds', 'ttl_seconds', 'tuner', 'is_valid']
    for key in expected_keys:
        assert key in cache_info, f"Expected key '{key}' not found in cache_info"

def test_cache_invalid_initially():
    """Test that cache is invalid when no data is cached"""
    from app import is_cache_valid
    assert not is_cache_valid(), "Cache should be invalid initially"

def test_update_and_validate_cache():
    """Test that updating cache makes it valid"""
    from app import update_cache, is_cache_valid, invalidate_cache
    
    # Start fresh
    invalidate_cache()
    assert not is_cache_valid(), "Cache should be invalid after invalidation"
    
    # Update cache with test data
    test_channels = [{'name': 'Test Channel', 'tvg_id': 'test1', 'url': 'http://test.m3u8', 'logo': ''}]
    test_epg = {'test1': [{'title': 'Test Program', 'desc': 'Test', 'start': None, 'stop': None}]}
    update_cache(test_channels, test_epg, 'Test Tuner')
    
    # Cache should now be valid
    assert is_cache_valid('Test Tuner'), "Cache should be valid after update"
    
    # Clean up
    invalidate_cache()

def test_cache_expiration():
    """Test that cache respects expiration time"""
    from app import update_cache, is_cache_valid, invalidate_cache, epg_cache_lock
    import time
    
    # Start fresh
    invalidate_cache()
    
    # Update cache with test data
    test_channels = [{'name': 'Test Channel', 'tvg_id': 'test1', 'url': 'http://test.m3u8', 'logo': ''}]
    test_epg = {'test1': [{'title': 'Test Program', 'desc': 'Test', 'start': None, 'stop': None}]}
    update_cache(test_channels, test_epg, 'Test Tuner')
    
    # Manually set expiration to past
    with epg_cache_lock:
        # Access the module-level epg_cache directly
        import app as app_module
        app_module.epg_cache['expiration'] = datetime.now(timezone.utc) - timedelta(seconds=1)
    
    # Cache should now be invalid due to expiration
    assert not is_cache_valid('Test Tuner'), "Cache should be invalid after expiration"
    
    # Clean up
    invalidate_cache()

def test_cache_tuner_mismatch():
    """Test that cache is invalid when tuner doesn't match"""
    from app import update_cache, is_cache_valid, invalidate_cache
    
    # Start fresh
    invalidate_cache()
    
    # Update cache for one tuner
    test_channels = [{'name': 'Test Channel', 'tvg_id': 'test1', 'url': 'http://test.m3u8', 'logo': ''}]
    test_epg = {'test1': [{'title': 'Test Program', 'desc': 'Test', 'start': None, 'stop': None}]}
    update_cache(test_channels, test_epg, 'Tuner1')
    
    # Should be valid for Tuner1
    assert is_cache_valid('Tuner1'), "Cache should be valid for Tuner1"
    
    # Should be invalid for a different tuner
    assert not is_cache_valid('Tuner2'), "Cache should be invalid for Tuner2"
    
    # Clean up
    invalidate_cache()

def test_invalidate_cache():
    """Test that invalidate_cache clears all cache data"""
    from app import update_cache, invalidate_cache, get_cache_info
    
    # Update cache with test data
    test_channels = [{'name': 'Test Channel', 'tvg_id': 'test1', 'url': 'http://test.m3u8', 'logo': ''}]
    test_epg = {'test1': [{'title': 'Test Program', 'desc': 'Test', 'start': None, 'stop': None}]}
    update_cache(test_channels, test_epg, 'Test Tuner')
    
    # Invalidate cache
    invalidate_cache()
    
    # Check that cache info reflects invalidation
    cache_info = get_cache_info()
    assert cache_info['cached_at'] is None, "cached_at should be None after invalidation"
    assert cache_info['expires_at'] is None, "expires_at should be None after invalidation"
    assert cache_info['tuner'] is None, "tuner should be None after invalidation"
    assert not cache_info['is_valid'], "is_valid should be False after invalidation"
