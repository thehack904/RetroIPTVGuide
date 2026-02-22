"""Test cases for tuner validation and M3U parsing enhancements"""
import pytest
import sys
import os

# Add parent directory to path to import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import _validate_url, parse_m3u
from unittest.mock import Mock, patch
from urllib.parse import urlparse


class TestURLValidation:
    """Test URL validation functionality"""
    
    def test_valid_http_url(self):
        """Test that valid HTTP URLs are accepted"""
        url = _validate_url("http://example.com/playlist.m3u", "M3U URL")
        assert url == "http://example.com/playlist.m3u"
    
    def test_valid_https_url(self):
        """Test that valid HTTPS URLs are accepted"""
        url = _validate_url("https://example.com/guide.xml", "XML URL")
        assert url == "https://example.com/guide.xml"
    
    def test_empty_url(self):
        """Test that empty URLs are rejected"""
        with pytest.raises(ValueError, match="cannot be empty"):
            _validate_url("", "Test URL")
    
    def test_none_url(self):
        """Test that None URLs are rejected"""
        with pytest.raises(ValueError, match="cannot be empty"):
            _validate_url(None, "Test URL")
    
    def test_url_without_scheme(self):
        """Test that URLs without http/https are rejected"""
        with pytest.raises(ValueError, match="must start with http"):
            _validate_url("ftp://example.com/file.m3u", "M3U URL")
    
    def test_url_without_host(self):
        """Test that malformed URLs without host are rejected"""
        with pytest.raises(ValueError, match="malformed"):
            _validate_url("http://", "Test URL")
    
    def test_url_strips_whitespace(self):
        """Test that URLs with whitespace are trimmed"""
        url = _validate_url("  http://example.com/playlist.m3u  ", "M3U URL")
        assert url == "http://example.com/playlist.m3u"


class TestM3UParsing:
    """Test M3U parsing functionality"""
    
    @patch('app.requests.get')
    def test_parse_standard_m3u(self, mock_get):
        """Test parsing standard M3U with #EXTINF entries"""
        mock_response = Mock()
        mock_response.text = """#EXTM3U
#EXTINF:-1 tvg-id="channel1" tvg-logo="http://example.com/logo.png",Channel One
http://example.com/stream1.m3u8
#EXTINF:-1 tvg-id="channel2",Channel Two
http://example.com/stream2.m3u8"""
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        channels = parse_m3u("http://example.com/playlist.m3u")
        
        assert len(channels) == 2
        assert channels[0]['name'] == 'Channel One'
        assert channels[0]['tvg_id'] == 'channel1'
        assert channels[0]['url'] == 'http://example.com/stream1.m3u8'
        assert channels[0]['logo'] == 'http://example.com/logo.png'
        
        assert channels[1]['name'] == 'Channel Two'
        assert channels[1]['tvg_id'] == 'channel2'
        assert channels[1]['url'] == 'http://example.com/stream2.m3u8'
    
    @patch('app.requests.get')
    def test_parse_single_channel_m3u8(self, mock_get):
        """Test parsing single-channel M3U8 (just a URL, no #EXTINF)"""
        mock_response = Mock()
        mock_response.text = "https://example.com/live/stream.m3u8"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        channels = parse_m3u("http://example.com/single.m3u")
        
        assert len(channels) == 1
        assert channels[0]['name'] == 'stream'
        assert channels[0]['url'] == 'https://example.com/live/stream.m3u8'
        assert channels[0]['logo'] == ''
        assert channels[0]['tvg_id'] == 'stream'
    
    @patch('app.requests.get')
    def test_parse_single_channel_with_complex_filename(self, mock_get):
        """Test parsing single-channel with complex filename"""
        mock_response = Mock()
        mock_response.text = "https://example.com/channels/live-tv-channel-1.m3u8"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        channels = parse_m3u("http://example.com/single.m3u")
        
        assert len(channels) == 1
        assert channels[0]['name'] == 'live-tv-channel-1'
        assert channels[0]['url'] == 'https://example.com/channels/live-tv-channel-1.m3u8'
    
    @patch('app.requests.get')
    def test_parse_single_channel_with_comments(self, mock_get):
        """Test parsing single-channel M3U8 that has comments but no #EXTINF"""
        mock_response = Mock()
        mock_response.text = """#EXTM3U
# This is a comment
https://example.com/stream.m3u8"""
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        channels = parse_m3u("http://example.com/single.m3u")
        
        assert len(channels) == 1
        assert channels[0]['name'] == 'stream'
        assert channels[0]['url'] == 'https://example.com/stream.m3u8'
    
    @patch('app.requests.get')
    def test_parse_empty_m3u(self, mock_get):
        """Test parsing empty M3U file"""
        mock_response = Mock()
        mock_response.text = ""
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        channels = parse_m3u("http://example.com/empty.m3u")
        
        assert len(channels) == 0
    
    @patch('app.requests.get')
    def test_parse_m3u_network_error(self, mock_get):
        """Test parsing M3U when network error occurs"""
        mock_get.side_effect = Exception("Network error")
        
        channels = parse_m3u("http://example.com/playlist.m3u")
        
        assert len(channels) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
