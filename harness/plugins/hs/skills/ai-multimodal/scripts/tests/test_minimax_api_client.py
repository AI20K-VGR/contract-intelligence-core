"""
Tests for minimax_api_client.py - HTTP utilities, auth, polling, downloads.

Kept to the cases that catch a real failure class (a documented httpx-vs-requests
redirect gap, a 200-but-error-code API contract, and an infinite-poll hang guard).
The rest of this file used to mock api_get/time.sleep and assert the mock was
called with the value it was told to return — a wrapper tested by simulating the
tool it wraps, never exercising a real HTTP boundary.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import respx  # noqa: F401 — provides the respx_mock fixture

sys.path.insert(0, str(Path(__file__).parent.parent))

import minimax_api_client as mac


class TestApiPost:
    def test_minimax_error_code_raises(self, respx_mock):
        # A 200 response can still carry a MiniMax-level error code — the
        # caller must not treat HTTP success as API success.
        respx_mock.post(f"{mac.BASE_URL}/endpoint").mock(
            return_value=httpx.Response(200, json={
                "base_resp": {"status_code": 1002, "status_msg": "Rate limit"}
            }))

        with pytest.raises(Exception, match="code 1002.*Rate limit"):
            mac.api_post("endpoint", {}, "api-key")

    def test_post_follows_redirects(self, monkeypatch):
        """httpx does not follow redirects by default (requests did) — a MiniMax
        endpoint 30x'ing without follow_redirects=True would surface as a bare
        redirect response instead of the real payload. Attribute-level double:
        follow_redirects is client/request-level behaviour respx cannot observe
        (see test_notify_remote.py's identical note)."""
        seen = {}

        def fake_post(url, **kwargs):
            seen.update(kwargs)
            return httpx.Response(200, json={"base_resp": {"status_code": 0}})

        monkeypatch.setattr(httpx, "post", fake_post)
        mac.api_post("endpoint", {}, "key")
        assert seen["follow_redirects"] is True


class TestPollAsyncTask:
    @patch('minimax_api_client.time.sleep')
    @patch('minimax_api_client.api_get')
    def test_poll_timeout(self, mock_get, mock_sleep):
        # Infinite-poll hang guard: a task stuck "Processing" forever must not
        # hang the caller past max_wait.
        mock_get.return_value = {"status": "Processing"}

        with pytest.raises(TimeoutError, match="timed out"):
            mac.poll_async_task("task4", "video_generation", "key",
                                 poll_interval=1, max_wait=3)
