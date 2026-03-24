"""Tests for CWE-601 open-redirect protection in _safe_next_url.

Verifies that the helper function used by the login route correctly blocks
external and protocol-relative redirect targets while allowing safe same-origin
relative paths.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import _safe_next_url


class TestSafeNextUrl:
    # ── Safe relative paths (should be returned unchanged) ────────────────────

    def test_simple_relative_path(self):
        assert _safe_next_url('/guide') == '/guide'

    def test_relative_path_with_query(self):
        assert _safe_next_url('/guide?tab=settings') == '/guide?tab=settings'

    def test_empty_string_returns_empty(self):
        assert _safe_next_url('') == ''

    def test_none_returns_empty(self):
        assert _safe_next_url(None) == ''

    def test_query_only_is_safe(self):
        assert _safe_next_url('?tab=1') == '?tab=1'

    def test_nested_path_is_safe(self):
        assert _safe_next_url('/admin/settings') == '/admin/settings'

    # ── Absolute URLs (must be rejected) ──────────────────────────────────────

    def test_http_url_rejected(self):
        assert _safe_next_url('http://evil.com') == ''

    def test_https_url_rejected(self):
        assert _safe_next_url('https://evil.com/phish') == ''

    def test_ftp_url_rejected(self):
        assert _safe_next_url('ftp://evil.com') == ''

    # ── Protocol-relative URLs (must be rejected) ──────────────────────────────

    def test_double_slash_rejected(self):
        assert _safe_next_url('//evil.com') == ''

    def test_double_slash_with_path_rejected(self):
        assert _safe_next_url('//evil.com/path') == ''

    # ── Protocol-relative bypass via extra slashes (must be rejected) ─────────

    def test_four_slashes_rejected(self):
        """'////evil.com' urlparse gives path='//evil.com' — must be rejected."""
        assert _safe_next_url('////evil.com') == ''

    def test_three_slashes_rejected(self):
        """'///evil.com' starts with '//' after normalisation so must be rejected."""
        assert _safe_next_url('///evil.com') == ''

    # ── Backslash-based bypass attempts (must be rejected) ────────────────────

    def test_two_backslashes_rejected(self):
        """'\\\\evil.com' → after normalise → '//evil.com' → netloc='evil.com' → rejected."""
        assert _safe_next_url('\\\\evil.com') == ''

    def test_four_backslashes_rejected(self):
        """'\\\\\\\\evil.com' → after normalise → '////evil.com' → path='//evil.com' → rejected."""
        assert _safe_next_url('\\\\\\\\evil.com') == ''

    def test_single_backslash_gives_relative_path(self):
        """'\\evil.com' → after normalise → '/evil.com' → safe relative path."""
        result = _safe_next_url('\\evil.com')
        assert result == '/evil.com'
