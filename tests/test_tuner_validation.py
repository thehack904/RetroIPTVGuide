# tests/test_tuner_validation.py
# Tests for tuner validation and M3U parsing improvements

import pytest
import sys
import os
import sqlite3
import tempfile
from unittest.mock import Mock, patch, MagicMock

# Add the parent directory to the path to import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module


class TestAddTunerValidation:
    """Test validation logic in add_tuner() function."""
    
    def setup_method(self):
        """Set up test database before each test."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        app_module.TUNER_DB = self.temp_db.name
        
        # Initialize database
        with sqlite3.connect(self.temp_db.name, timeout=10) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS tuners
                        (name TEXT PRIMARY KEY, xml TEXT, m3u TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS settings
                        (key TEXT PRIMARY KEY, value TEXT)''')
            conn.commit()
    
    def teardown_method(self):
        """Clean up test database after each test."""
        try:
            os.unlink(self.temp_db.name)
        except OSError:
            pass
    
    def test_duplicate_name_prevention(self):
        """Test that duplicate tuner names are rejected."""
        # Add a tuner first
        with patch('app.requests.head') as mock_head:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_head.return_value = mock_response
            
            app_module.add_tuner("TestTuner", "http://example.com/epg.xml", "http://example.com/playlist.m3u")
        
        # Try to add duplicate
        with pytest.raises(ValueError, match="Tuner 'TestTuner' already exists"):
            with patch('app.requests.head') as mock_head:
                mock_response = Mock()
                mock_response.raise_for_status = Mock()
                mock_head.return_value = mock_response
                
                app_module.add_tuner("TestTuner", "http://example.com/epg2.xml", "http://example.com/playlist2.m3u")
    
    def test_m3u_url_required(self):
        """Test that M3U URL is required."""
        with pytest.raises(ValueError, match="M3U URL is required"):
            app_module.add_tuner("TestTuner", "http://example.com/epg.xml", "")
        
        with pytest.raises(ValueError, match="M3U URL is required"):
            app_module.add_tuner("TestTuner", "http://example.com/epg.xml", "   ")
    
    def test_m3u_url_must_be_http_or_https(self):
        """Test that M3U URL must start with http:// or https://."""
        with pytest.raises(ValueError, match="M3U URL must start with http:// or https://"):
            app_module.add_tuner("TestTuner", "http://example.com/epg.xml", "ftp://example.com/playlist.m3u")
        
        with pytest.raises(ValueError, match="M3U URL must start with http:// or https://"):
            app_module.add_tuner("TestTuner", "http://example.com/epg.xml", "/local/playlist.m3u")
    
    def test_xml_url_must_be_http_or_https_if_provided(self):
        """Test that XML URL must start with http:// or https:// if provided."""
        with pytest.raises(ValueError, match="XML URL must start with http:// or https://"):
            with patch('app.requests.head') as mock_head:
                mock_response = Mock()
                mock_response.raise_for_status = Mock()
                mock_head.return_value = mock_response
                
                app_module.add_tuner("TestTuner", "ftp://example.com/epg.xml", "http://example.com/playlist.m3u")
    
    def test_xml_url_can_be_empty(self):
        """Test that XML URL can be empty or whitespace."""
        with patch('app.requests.head') as mock_head:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_head.return_value = mock_response
            
            # Should not raise an error
            app_module.add_tuner("TestTuner1", "", "http://example.com/playlist.m3u")
            app_module.add_tuner("TestTuner2", "   ", "http://example.com/playlist2.m3u")
    
    def test_url_reachability_check(self):
        """Test that unreachable URLs are rejected."""
        import requests
        with patch('app.requests.head') as mock_head:
            mock_head.side_effect = requests.RequestException("Connection refused")
            
            with pytest.raises(ValueError, match="M3U URL unreachable"):
                app_module.add_tuner("TestTuner", "http://example.com/epg.xml", "http://unreachable.example.com/playlist.m3u")
    
    def test_successful_tuner_addition(self):
        """Test successful tuner addition with valid inputs."""
        with patch('app.requests.head') as mock_head:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_head.return_value = mock_response
            
            app_module.add_tuner("ValidTuner", "http://example.com/epg.xml", "http://example.com/playlist.m3u")
            
            # Verify tuner was added
            tuners = app_module.get_tuners()
            assert "ValidTuner" in tuners
            assert tuners["ValidTuner"]["xml"] == "http://example.com/epg.xml"
            assert tuners["ValidTuner"]["m3u"] == "http://example.com/playlist.m3u"


class TestSingleChannelM3U8:
    """Test single-channel M3U8 playlist parsing."""
    
    def test_single_channel_m3u8_with_simple_url(self):
        """Test parsing a simple M3U8 with just one stream URL."""
        m3u_content = """#EXTM3U
https://example.com/live/stream.m3u8"""
        
        with patch('app.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = m3u_content
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            channels = app_module.parse_m3u("http://example.com/single.m3u8")
            
            assert len(channels) == 1
            assert channels[0]['url'] == "https://example.com/live/stream.m3u8"
            assert channels[0]['tvg_id'] == 'stream_1'
            assert channels[0]['logo'] == ''
            # Name should be extracted from URL
            assert channels[0]['name'] == 'Stream'
    
    def test_single_channel_m3u8_with_descriptive_name(self):
        """Test that channel name is extracted from URL path."""
        m3u_content = """#EXTM3U
https://example.com/live/my_awesome_channel.m3u8"""
        
        with patch('app.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = m3u_content
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            channels = app_module.parse_m3u("http://example.com/single.m3u8")
            
            assert len(channels) == 1
            assert channels[0]['name'] == 'My Awesome Channel'
    
    def test_single_channel_m3u8_with_no_extinf(self):
        """Test M3U8 without any #EXTINF tags."""
        m3u_content = """https://example.com/live/stream.m3u8"""
        
        with patch('app.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = m3u_content
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            channels = app_module.parse_m3u("http://example.com/single.m3u8")
            
            assert len(channels) == 1
            assert channels[0]['url'] == "https://example.com/live/stream.m3u8"
    
    def test_single_channel_default_name(self):
        """Test default name when URL doesn't provide a good name."""
        m3u_content = """https://example.com/"""
        
        with patch('app.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = m3u_content
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            channels = app_module.parse_m3u("http://example.com/single.m3u8")
            
            assert len(channels) == 1
            assert channels[0]['name'] == 'Live Stream'
    
    def test_multiple_urls_not_single_channel(self):
        """Test that multiple URLs without #EXTINF don't parse as single channel."""
        m3u_content = """https://example.com/stream1.m3u8
https://example.com/stream2.m3u8"""
        
        with patch('app.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = m3u_content
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            channels = app_module.parse_m3u("http://example.com/multi.m3u8")
            
            # Should return empty since it's not a valid single-channel playlist
            assert len(channels) == 0
    
    def test_multi_channel_m3u_still_works(self):
        """Test that existing multi-channel M3U parsing still works."""
        m3u_content = """#EXTM3U
#EXTINF:-1 tvg-id="ch1" tvg-logo="http://example.com/logo1.png",Channel 1
http://example.com/stream1.m3u8
#EXTINF:-1 tvg-id="ch2" tvg-logo="http://example.com/logo2.png",Channel 2
http://example.com/stream2.m3u8"""
        
        with patch('app.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = m3u_content
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            channels = app_module.parse_m3u("http://example.com/multi.m3u8")
            
            assert len(channels) == 2
            assert channels[0]['name'] == 'Channel 1'
            assert channels[0]['tvg_id'] == 'ch1'
            assert channels[0]['logo'] == 'http://example.com/logo1.png'
            assert channels[0]['url'] == 'http://example.com/stream1.m3u8'
            assert channels[1]['name'] == 'Channel 2'
            assert channels[1]['tvg_id'] == 'ch2'
    
    def test_empty_m3u_returns_empty_channels(self):
        """Test that an empty M3U returns empty channel list."""
        m3u_content = ""
        
        with patch('app.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = m3u_content
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            channels = app_module.parse_m3u("http://example.com/empty.m3u8")
            
            assert len(channels) == 0
