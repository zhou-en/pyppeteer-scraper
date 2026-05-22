"""
End-to-end tests for the Canada IRCC processing-times scraper.

All external I/O (Playwright browser, Slack, file-based storage) is mocked.
The fill_form_and_get_result function is mocked at the orchestration boundary
so the tests focus on diff / state-file / notification behavior. The actual
DOM-level form filling is exercised by running the scraper against the real
page during local verification.
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.insert(0, parent)

# Ensure env vars exist BEFORE service.alert is imported (it sys.exit(1)s otherwise).
os.environ.setdefault("SLACK_API_TOKEN", "test-token")
os.environ.setdefault("CHANNEL_ID", "test-channel")

from scraper import canada_ircc
from scraper.canada_ircc import has_changed, load_state, save_state


SAMPLE_RESULT = {
    "estimated_time": "We need more time to process your application",
    "last_updated": "May 12, 2026",
    "people_ahead": "About 400 people ahead of you",
    "total_waiting": "About 14,000 people waiting",
}


@patch("slack.WebClient")
class TestHasChanged(unittest.TestCase):
    """Unit tests for the diff function."""

    def test_no_cached_state_is_change(self, _wc):
        self.assertTrue(has_changed(SAMPLE_RESULT, None))

    def test_identical_is_no_change(self, _wc):
        self.assertFalse(has_changed(SAMPLE_RESULT, dict(SAMPLE_RESULT)))

    def test_people_ahead_change(self, _wc):
        cached = dict(SAMPLE_RESULT, people_ahead="About 380 people ahead of you")
        self.assertTrue(has_changed(SAMPLE_RESULT, cached))

    def test_last_updated_change(self, _wc):
        cached = dict(SAMPLE_RESULT, last_updated="April 14, 2026")
        self.assertTrue(has_changed(SAMPLE_RESULT, cached))

    def test_total_waiting_change(self, _wc):
        cached = dict(SAMPLE_RESULT, total_waiting="About 13,500 people waiting")
        self.assertTrue(has_changed(SAMPLE_RESULT, cached))

    def test_estimated_time_change(self, _wc):
        cached = dict(SAMPLE_RESULT, estimated_time="6 months")
        self.assertTrue(has_changed(SAMPLE_RESULT, cached))


@patch("slack.WebClient")
class TestStateFileIO(unittest.TestCase):
    """Unit tests for load_state / save_state with a temp STATE_FILE."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "ircc_state.json")
        self._orig = canada_ircc.STATE_FILE
        canada_ircc.STATE_FILE = self.state_path

    def tearDown(self):
        canada_ircc.STATE_FILE = self._orig
        if os.path.exists(self.state_path):
            os.remove(self.state_path)
        # storage/ subdir created by save_state when STATE_FILE is "storage/..."
        # but here STATE_FILE is absolute, so nothing extra to clean.
        os.rmdir(self.tmpdir)

    def test_load_state_missing_file(self, _wc):
        self.assertIsNone(load_state())

    def test_save_then_load_roundtrip(self, _wc):
        save_state(SAMPLE_RESULT)
        self.assertEqual(load_state(), SAMPLE_RESULT)

    def test_load_state_corrupt_file_returns_none(self, _wc):
        with open(self.state_path, "w") as fh:
            fh.write("{ not valid JSON")
        self.assertIsNone(load_state())

    def test_load_state_empty_file_returns_none(self, _wc):
        open(self.state_path, "w").close()  # touch empty
        self.assertIsNone(load_state())


@patch("slack.WebClient")
class TestRunE2E(unittest.TestCase):
    """End-to-end tests for canada_ircc.run() orchestration."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "ircc_state.json")
        self._orig_state = canada_ircc.STATE_FILE
        canada_ircc.STATE_FILE = self.state_path

    def tearDown(self):
        canada_ircc.STATE_FILE = self._orig_state
        if os.path.exists(self.state_path):
            os.remove(self.state_path)
        os.rmdir(self.tmpdir)

    def _run(self, coro):
        return asyncio.run(coro)

    def _patch_playwright(self, mock_pw, current_result):
        """Wire async_playwright so fill_form_and_get_result returns current_result."""
        pw_instance = AsyncMock()
        browser = AsyncMock()
        page = MagicMock()  # page passed to fill_form_and_get_result (mocked separately)
        pw_instance.chromium.launch.return_value = browser
        browser.new_page.return_value = page
        mock_pw.return_value.__aenter__.return_value = pw_instance
        mock_pw.return_value.__aexit__.return_value = None
        return pw_instance, browser, page

    @patch("scraper.canada_ircc.send_ircc_status_card")
    @patch("scraper.canada_ircc.fill_form_and_get_result")
    @patch("playwright.async_api.async_playwright")
    def test_first_run_posts_and_writes_state(
        self, mock_pw, mock_fill, mock_card, _wc
    ):
        """No state file → post status card, write state file."""
        self._patch_playwright(mock_pw, SAMPLE_RESULT)
        mock_fill.return_value = SAMPLE_RESULT

        self._run(canada_ircc.run())

        mock_card.assert_called_once()
        kwargs = mock_card.call_args.kwargs
        self.assertEqual(kwargs["estimated_time"], SAMPLE_RESULT["estimated_time"])
        self.assertEqual(kwargs["people_ahead"], SAMPLE_RESULT["people_ahead"])
        self.assertEqual(kwargs["total_waiting"], SAMPLE_RESULT["total_waiting"])
        self.assertEqual(kwargs["last_updated"], SAMPLE_RESULT["last_updated"])
        self.assertEqual(kwargs["config_label"], canada_ircc.CONFIG_LABEL)
        self.assertEqual(kwargs["source_url"], canada_ircc.TARGET_URL)

        with open(self.state_path, "r") as fh:
            self.assertEqual(json.load(fh), SAMPLE_RESULT)

    @patch("scraper.canada_ircc.send_ircc_status_card")
    @patch("scraper.canada_ircc.fill_form_and_get_result")
    @patch("playwright.async_api.async_playwright")
    def test_no_change_is_silent(self, mock_pw, mock_fill, mock_card, _wc):
        """Re-run with identical data → no Slack call, state file unchanged."""
        with open(self.state_path, "w") as fh:
            json.dump(SAMPLE_RESULT, fh)
        mtime_before = os.path.getmtime(self.state_path)

        self._patch_playwright(mock_pw, SAMPLE_RESULT)
        mock_fill.return_value = SAMPLE_RESULT

        self._run(canada_ircc.run())

        mock_card.assert_not_called()
        with open(self.state_path, "r") as fh:
            self.assertEqual(json.load(fh), SAMPLE_RESULT)

    @patch("scraper.canada_ircc.send_ircc_status_card")
    @patch("scraper.canada_ircc.fill_form_and_get_result")
    @patch("playwright.async_api.async_playwright")
    def test_change_posts_and_updates_state(
        self, mock_pw, mock_fill, mock_card, _wc
    ):
        """One field changed → post status card, state file updated."""
        cached = dict(SAMPLE_RESULT, people_ahead="About 500 people ahead of you")
        with open(self.state_path, "w") as fh:
            json.dump(cached, fh)

        self._patch_playwright(mock_pw, SAMPLE_RESULT)
        mock_fill.return_value = SAMPLE_RESULT

        self._run(canada_ircc.run())

        mock_card.assert_called_once()
        self.assertEqual(
            mock_card.call_args.kwargs["people_ahead"],
            "About 400 people ahead of you",
        )
        with open(self.state_path, "r") as fh:
            self.assertEqual(json.load(fh), SAMPLE_RESULT)

    @patch("scraper.canada_ircc.send_api_error_alert")
    @patch("scraper.canada_ircc.send_ircc_status_card")
    @patch("scraper.canada_ircc.fill_form_and_get_result")
    @patch("playwright.async_api.async_playwright")
    def test_parse_failure_sends_error_and_exits(
        self, mock_pw, mock_fill, mock_card, mock_err, _wc
    ):
        """fill_form_and_get_result raises → send_api_error_alert, sys.exit(1), no status card."""
        self._patch_playwright(mock_pw, SAMPLE_RESULT)
        mock_fill.side_effect = RuntimeError("missing 'Estimated time left' selector")

        with self.assertRaises(SystemExit) as cm:
            self._run(canada_ircc.run())
        self.assertEqual(cm.exception.code, 1)

        mock_err.assert_called_once()
        args = mock_err.call_args[0]
        self.assertEqual(args[0], "Canada IRCC")
        self.assertIn("missing", args[2])
        mock_card.assert_not_called()
        self.assertFalse(os.path.exists(self.state_path))

    @patch("scraper.canada_ircc.send_api_error_alert")
    @patch("scraper.canada_ircc.send_ircc_status_card")
    @patch("scraper.canada_ircc.fill_form_and_get_result")
    @patch("playwright.async_api.async_playwright")
    def test_browser_timeout_sends_error_and_exits(
        self, mock_pw, mock_fill, mock_card, mock_err, _wc
    ):
        """Playwright timeout → send_api_error_alert, sys.exit(1)."""
        self._patch_playwright(mock_pw, SAMPLE_RESULT)
        mock_fill.side_effect = TimeoutError("page.goto timed out after 60000ms")

        with self.assertRaises(SystemExit):
            self._run(canada_ircc.run())

        mock_err.assert_called_once()
        self.assertIn("timed out", mock_err.call_args[0][2])
        mock_card.assert_not_called()


if __name__ == "__main__":
    unittest.main()
