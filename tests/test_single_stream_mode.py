"""Test cases for single-stream mode functionality"""
import pytest
import sys
import os

# Add parent directory to path to import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, init_db, init_tuners_db, add_tuner, get_tuners
import tempfile
import sqlite3


class TestSingleStreamMode:
    """Test single-stream mode functionality"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up test database before each test and clean up after"""
        # Create temporary database files
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_tuner_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        
        # Store original database paths
        import app as app_module
        self.orig_db = app_module.DATABASE
        self.orig_tuner_db = app_module.TUNER_DB
        
        # Set temporary database paths
        app_module.DATABASE = self.temp_db.name
        app_module.TUNER_DB = self.temp_tuner_db.name
        
        # Initialize databases
        init_db()
        init_tuners_db()
        
        yield
        
        # Clean up
        app_module.DATABASE = self.orig_db
        app_module.TUNER_DB = self.orig_tuner_db
        os.unlink(self.temp_db.name)
        os.unlink(self.temp_tuner_db.name)
    
    def test_add_single_stream_tuner(self):
        """Test adding a tuner in single-stream mode"""
        # Single stream mode uses the same URL for both XML and M3U
        stream_url = "https://example.com/live/stream.m3u8"
        tuner_name = "Test Single Stream"
        
        # Add tuner with same URL for both fields (simulating single-stream mode)
        add_tuner(tuner_name, stream_url, stream_url)
        
        # Verify tuner was added correctly
        tuners = get_tuners()
        assert tuner_name in tuners
        assert tuners[tuner_name]['xml'] == stream_url
        assert tuners[tuner_name]['m3u'] == stream_url
    
    def test_add_standard_mode_tuner(self):
        """Test adding a tuner in standard mode"""
        xml_url = "https://example.com/guide.xml"
        m3u_url = "https://example.com/playlist.m3u"
        tuner_name = "Test Standard"
        
        # Add tuner with different URLs (standard mode)
        add_tuner(tuner_name, xml_url, m3u_url)
        
        # Verify tuner was added correctly
        tuners = get_tuners()
        assert tuner_name in tuners
        assert tuners[tuner_name]['xml'] == xml_url
        assert tuners[tuner_name]['m3u'] == m3u_url
    
    def test_duplicate_tuner_name(self):
        """Test that duplicate tuner names are rejected"""
        tuner_name = "Duplicate Test"
        url = "https://example.com/stream.m3u8"
        
        # Add first tuner
        add_tuner(tuner_name, url, url)
        
        # Try to add duplicate - should raise ValueError
        with pytest.raises(ValueError, match="already exists"):
            add_tuner(tuner_name, url, url)
    
    def test_empty_urls(self):
        """Test that empty URLs are rejected"""
        with pytest.raises(ValueError, match="cannot be empty"):
            add_tuner("Test Tuner", "", "https://example.com/playlist.m3u")
        
        with pytest.raises(ValueError, match="cannot be empty"):
            add_tuner("Test Tuner", "https://example.com/guide.xml", "")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
