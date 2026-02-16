"""
End-to-end tests for the Home Depot workshop scraper.

Uses the JSON fixtures:
  - homedepot_sample_response.json   (API workshop listing)
  - homedepot_registration_payload.json  (registration POST body)

All external I/O (Playwright HTTP, Slack, file-based storage) is mocked so
the tests run offline without side-effects.
"""

import asyncio
import json
import os
import sys
import unittest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

import requests

# ---------------------------------------------------------------------------
# Path setup – mirrors the convention used in the production code
# ---------------------------------------------------------------------------
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.insert(0, parent)

from scraper.home_depo import (
    register_home_depot_workshop,
    run2,
    should_register_workshop,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------
FIXTURE_DIR = os.path.dirname(os.path.realpath(__file__))


def _load_fixture(filename: str) -> dict:
    path = os.path.join(FIXTURE_DIR, filename)
    with open(path, "r") as fh:
        return json.load(fh)


def _build_playwright_mocks(response_body, *, status=200, headers=None):
    """
    Return a (mock_playwright, mock_context, mock_response) triple
    wired up so that ``async with async_playwright() as pw`` works.
    """
    headers = headers or {"Content-Type": "application/json"}

    mock_response = AsyncMock()
    mock_response.status = status
    mock_response.headers = headers

    if isinstance(response_body, (dict, list)):
        text = json.dumps(response_body)
        mock_response.text.return_value = text
        mock_response.json.return_value = response_body
    elif isinstance(response_body, str):
        mock_response.text.return_value = response_body
        # If the string isn't valid JSON, make .json() raise
        try:
            parsed = json.loads(response_body)
            mock_response.json.return_value = parsed
        except json.JSONDecodeError as exc:
            mock_response.json.side_effect = exc
    else:
        mock_response.text.return_value = ""
        mock_response.json.side_effect = json.JSONDecodeError("empty", "", 0)

    mock_context = AsyncMock()
    mock_context.get.return_value = mock_response

    mock_pw_instance = AsyncMock()
    mock_pw_instance.request.new_context.return_value = mock_context

    mock_playwright = AsyncMock()
    mock_playwright.return_value.__aenter__.return_value = mock_pw_instance

    return mock_playwright, mock_context, mock_response


# =========================================================================
# Test classes
# =========================================================================


@patch("slack.WebClient")  # prevent real Slack client init at import time
class TestShouldRegisterWorkshop(unittest.TestCase):
    """Unit-level tests for the should_register_workshop decision function."""

    def test_matching_criteria(self, _mock_wc):
        """Workshop starts at 08:30 and at least 1 seat taken → should register."""
        ok, reason = should_register_workshop(
            workshop_id="MWBT0005",
            start_time="2026-03-14T08:30:00-0400",
            attendee_limit=96,
            remaining_seats=19,
        )
        self.assertTrue(ok)
        self.assertIn("8:30", reason)

    def test_wrong_start_time(self, _mock_wc):
        """Start time is NOT 08:30 → should NOT register."""
        ok, reason = should_register_workshop(
            workshop_id="MWBT0006",
            start_time="2026-03-14T10:30:00-0400",
            attendee_limit=96,
            remaining_seats=19,
        )
        self.assertFalse(ok)
        self.assertIn("8:30", reason)

    def test_no_one_registered_yet(self, _mock_wc):
        """No seats taken → should NOT register (waits for first registrant)."""
        ok, reason = should_register_workshop(
            workshop_id="MWBT0005",
            start_time="2026-03-14T08:30:00-0400",
            attendee_limit=96,
            remaining_seats=96,  # no one has registered
        )
        self.assertFalse(ok)
        self.assertIn("No one has registered", reason)

    def test_exactly_one_registered(self, _mock_wc):
        """Exactly 1 seat taken → should register."""
        ok, reason = should_register_workshop(
            workshop_id="MWBT0005",
            start_time="2026-03-14T08:30:00-0400",
            attendee_limit=96,
            remaining_seats=95,
        )
        self.assertTrue(ok)


# -------------------------------------------------------------------------
# Registration
# -------------------------------------------------------------------------
@patch("slack.WebClient")
class TestRegisterWorkshopE2E(unittest.TestCase):
    """
    End-to-end tests for register_home_depot_workshop() using the real
    registration payload fixture.
    """

    def setUp(self):
        self.payload_fixture = _load_fixture("homedepot_registration_payload.json")
        self.sample_response = _load_fixture("homedepot_sample_response.json")
        # Extract the first event from the fixture for realistic params
        first_event = self.sample_response["workshopEventWsDTO"][0]
        self.event_code = first_event["code"]  # "MWBT0005"
        self.workshop_event_id = first_event["eventType"]["workshopEventId"]  # "WS00037"

    @patch("service.alert.send_slack_message")
    @patch("service.alert.send_api_error_alert")
    @patch("requests.post")
    def test_successful_registration_with_fixture_data(
        self, mock_post, mock_api_alert, mock_slack, _wc
    ):
        """POST succeeds → returns (True, response_text)."""
        success_body = {"status": "OK", "message": "Registration successful"}
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = success_body
        mock_resp.text = json.dumps(success_body)
        mock_post.return_value = mock_resp

        ok, text = register_home_depot_workshop(
            event_code=self.event_code,
            workshop_event_id=self.workshop_event_id,
            first_name=self.payload_fixture["customer"]["firstName"],
            last_name=self.payload_fixture["customer"]["lastName"],
            email=self.payload_fixture["customer"]["email"],
            store_id=self.payload_fixture["store"],
            participant_count=self.payload_fixture["participantCount"],
        )

        self.assertTrue(ok)
        # URL should contain both IDs
        call_url = mock_post.call_args[0][0]
        self.assertIn(self.workshop_event_id, call_url)
        self.assertIn(self.event_code, call_url)

        # The sent payload must exactly match the registration fixture
        sent_json = mock_post.call_args[1]["json"]
        self.assertEqual(sent_json, self.payload_fixture)

    @patch("service.alert.send_slack_message")
    @patch("service.alert.send_api_error_alert")
    @patch("requests.post")
    def test_failed_registration_returns_false(
        self, mock_post, mock_api_alert, mock_slack, _wc
    ):
        """HTTP 400 → returns (False, ...)."""
        fail_body = {"error": "Workshop is full"}
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 400
        mock_resp.json.return_value = fail_body
        mock_resp.text = json.dumps(fail_body)
        mock_post.return_value = mock_resp

        ok, text = register_home_depot_workshop(
            event_code=self.event_code,
            workshop_event_id=self.workshop_event_id,
        )

        self.assertFalse(ok)
        mock_api_alert.assert_called_once()
        self.assertIn("failed", mock_api_alert.call_args[0][1].lower())

    @patch("service.alert.send_slack_message")
    @patch("service.alert.send_api_error_alert")
    @patch("requests.post")
    def test_network_exception(self, mock_post, mock_api_alert, mock_slack, _wc):
        """Network exception → returns (False, error_string)."""
        mock_post.side_effect = requests.exceptions.ConnectionError("DNS failed")

        ok, text = register_home_depot_workshop(
            event_code=self.event_code,
            workshop_event_id=self.workshop_event_id,
        )

        self.assertFalse(ok)
        self.assertIn("DNS failed", text)
        mock_api_alert.assert_called_once()

    @patch("service.alert.send_slack_message")
    @patch("service.alert.send_api_error_alert")
    @patch("requests.post")
    def test_dry_run_does_not_call_api(
        self, mock_post, mock_api_alert, mock_slack, _wc
    ):
        """dry_run=True → no HTTP call is made."""
        ok, text = register_home_depot_workshop(
            event_code=self.event_code,
            workshop_event_id=self.workshop_event_id,
            dry_run=True,
        )

        self.assertTrue(ok)
        mock_post.assert_not_called()
        response = json.loads(text)
        self.assertTrue(response["dry_run"])


# -------------------------------------------------------------------------
# Full run2() pipeline
# -------------------------------------------------------------------------
@patch("slack.WebClient")
class TestRun2E2E(unittest.TestCase):
    """
    End-to-end tests for run2() – the main scraper entry-point.
    Loads the *real* sample response fixture and verifies the full pipeline
    of parsing → filtering → alerting → registration.
    """

    def setUp(self):
        self.sample_response = _load_fixture("homedepot_sample_response.json")

    # -- helpers ----------------------------------------------------------

    def _run(self, coro):
        """Run an async coroutine in a fresh event loop."""
        return asyncio.run(coro)

    # -- happy-path scenarios ---------------------------------------------

    @patch("service.alert.save_registered_workshop")
    @patch("service.alert.is_workshop_registered", return_value=False)
    @patch("scraper.home_depo.register_home_depot_workshop", return_value=(True, "OK"))
    @patch("service.alert.send_urgent_workshop_alert")
    @patch("scraper.home_depo.send_slack_message")
    @patch("service.alert.send_slack_message")
    @patch("scraper.home_depo.update_last_alert_date")
    @patch("scraper.home_depo.get_last_alert_date", return_value=None)
    @patch("playwright.async_api.async_playwright")
    def test_full_pipeline_registers_eligible_workshop(
        self,
        mock_pw,
        mock_get_date,
        mock_update_date,
        mock_slack_svc,
        mock_slack_scraper,
        mock_urgent,
        mock_register,
        mock_is_registered,
        mock_save_reg,
        _wc,
    ):
        """
        MWBT0005 (08:30, 19 remaining out of 96, KID, ACTIVE) should
        trigger an alert AND an auto-registration.

        MWBT0006 (10:30, 0 remaining) should be skipped (seats=0).
        """
        pw, ctx, resp = _build_playwright_mocks(self.sample_response)
        mock_pw.return_value.__aenter__.return_value = (
            pw.return_value.__aenter__.return_value
        )
        mock_pw.return_value.__aenter__.return_value.request.new_context.return_value = (
            ctx
        )

        # Override the mock returned by the decorator
        mock_pw.return_value = pw.return_value

        # Re-wire so async with works
        mock_pw.return_value.__aenter__.return_value = (
            pw.return_value.__aenter__.return_value
        )

        self._run(run2())

        # Slack alert should have been sent for the eligible workshop
        self.assertTrue(mock_slack_scraper.called or mock_slack_svc.called)

        # Urgent alert should have been sent
        mock_urgent.assert_called()
        urgent_args = mock_urgent.call_args[0]
        workshop_details = urgent_args[0]
        self.assertEqual(workshop_details["title"], "Build a Leprechaun Trap")
        self.assertEqual(workshop_details["event_code"], "WS00037")
        self.assertEqual(workshop_details["seats_left"], 19)

        # Last alert date should have been updated
        mock_update_date.assert_called()

        # Registration should be attempted for MWBT0005 (08:30, seats available)
        mock_register.assert_called_once_with("MWBT0005", "WS00037")

        # Successful registration should be saved with exact data
        # that ends up in storage/registered_workshops.json
        mock_save_reg.assert_called_once()
        save_kwargs = mock_save_reg.call_args[1]
        self.assertEqual(save_kwargs["scraper_name"], "home_depo")
        self.assertEqual(save_kwargs["workshop_event_id"], "WS00037")
        self.assertEqual(save_kwargs["workshop_id"], "MWBT0005")
        self.assertEqual(save_kwargs["title"], "Build a Leprechaun Trap")
        # event_date should be the human-readable formatted date string
        # produced by strftime("%A, %B %d, %Y at %I:%M %p")
        self.assertIn("March", save_kwargs["event_date"])
        self.assertIn("2026", save_kwargs["event_date"])
        self.assertIn("08:30", save_kwargs["event_date"])

    @patch("service.alert.save_registered_workshop")
    @patch("service.alert.is_workshop_registered", return_value=True)  # Already registered!
    @patch("scraper.home_depo.register_home_depot_workshop")
    @patch("service.alert.send_urgent_workshop_alert")
    @patch("scraper.home_depo.send_slack_message")
    @patch("service.alert.send_slack_message")
    @patch("scraper.home_depo.update_last_alert_date")
    @patch("scraper.home_depo.get_last_alert_date", return_value=None)
    @patch("playwright.async_api.async_playwright")
    def test_skips_already_registered_workshop(
        self,
        mock_pw,
        mock_get_date,
        mock_update_date,
        mock_slack_svc,
        mock_slack_scraper,
        mock_urgent,
        mock_register,
        mock_is_registered,
        mock_save_reg,
        _wc,
    ):
        """
        When is_workshop_registered() returns True, registration should be
        skipped entirely.
        """
        pw, ctx, resp = _build_playwright_mocks(self.sample_response)
        mock_pw.return_value = pw.return_value
        mock_pw.return_value.__aenter__.return_value = (
            pw.return_value.__aenter__.return_value
        )

        self._run(run2())

        # Alert still sent (registration check happens AFTER alerting in the code)
        self.assertTrue(mock_slack_scraper.called or mock_slack_svc.called)

        # is_workshop_registered should have been called with the correct args
        # for the 8:30 workshop (MWBT0005 → event_code WS00037)
        mock_is_registered.assert_any_call("home_depo", "WS00037")

        # But registration should NOT be attempted since it's already registered
        mock_register.assert_not_called()
        mock_save_reg.assert_not_called()

    @patch("service.alert.save_registered_workshop")
    @patch("service.alert.is_workshop_registered", return_value=False)
    @patch("scraper.home_depo.register_home_depot_workshop")
    @patch("service.alert.send_urgent_workshop_alert")
    @patch("scraper.home_depo.send_slack_message")
    @patch("service.alert.send_slack_message")
    @patch("scraper.home_depo.update_last_alert_date")
    @patch("scraper.home_depo.get_last_alert_date")
    @patch("playwright.async_api.async_playwright")
    def test_skips_when_alert_already_sent_today(
        self,
        mock_pw,
        mock_get_date,
        mock_update_date,
        mock_slack_svc,
        mock_slack_scraper,
        mock_urgent,
        mock_register,
        mock_is_registered,
        mock_save_reg,
        _wc,
    ):
        """
        If an alert was already sent today, the workshop should be skipped
        (no new alert, no registration attempt).
        """
        mock_get_date.return_value = date.today()  # Already alerted today

        pw, ctx, resp = _build_playwright_mocks(self.sample_response)
        mock_pw.return_value = pw.return_value
        mock_pw.return_value.__aenter__.return_value = (
            pw.return_value.__aenter__.return_value
        )

        self._run(run2())

        # No slack messages should be sent
        mock_slack_scraper.assert_not_called()
        mock_urgent.assert_not_called()
        mock_update_date.assert_not_called()
        mock_register.assert_not_called()

    @patch("service.alert.save_registered_workshop")
    @patch("service.alert.is_workshop_registered", return_value=False)
    @patch("scraper.home_depo.register_home_depot_workshop", return_value=(False, "Error"))
    @patch("service.alert.send_urgent_workshop_alert")
    @patch("scraper.home_depo.send_slack_message")
    @patch("service.alert.send_slack_message")
    @patch("scraper.home_depo.update_last_alert_date")
    @patch("scraper.home_depo.get_last_alert_date", return_value=None)
    @patch("playwright.async_api.async_playwright")
    def test_failed_registration_not_saved(
        self,
        mock_pw,
        mock_get_date,
        mock_update_date,
        mock_slack_svc,
        mock_slack_scraper,
        mock_urgent,
        mock_register,
        mock_is_registered,
        mock_save_reg,
        _wc,
    ):
        """
        When registration fails, save_registered_workshop() should NOT be called.
        An error Slack message should be sent instead.
        """
        pw, ctx, resp = _build_playwright_mocks(self.sample_response)
        mock_pw.return_value = pw.return_value
        mock_pw.return_value.__aenter__.return_value = (
            pw.return_value.__aenter__.return_value
        )

        self._run(run2())

        # Registration was attempted
        mock_register.assert_called_once()

        # But NOT saved because it failed
        mock_save_reg.assert_not_called()

        # An error slack message should have been sent (the code sends one)
        # The scraper sends error messages via send_slack_message
        self.assertTrue(mock_slack_scraper.called)

    # -- workshop filtering scenarios -------------------------------------

    @patch("service.alert.send_urgent_workshop_alert")
    @patch("scraper.home_depo.send_slack_message")
    @patch("service.alert.send_slack_message")
    @patch("scraper.home_depo.update_last_alert_date")
    @patch("scraper.home_depo.get_last_alert_date", return_value=None)
    @patch("playwright.async_api.async_playwright")
    def test_skips_fully_booked_workshop(
        self,
        mock_pw,
        mock_get_date,
        mock_update_date,
        mock_slack_svc,
        mock_slack_scraper,
        mock_urgent,
        _wc,
    ):
        """
        A workshop with remainingSeats=0 should be skipped entirely.
        The second event in the fixture (MWBT0006) has 0 remaining seats.
        If we remove the first event, nothing should be processed.
        """
        response = _load_fixture("homedepot_sample_response.json")
        # Keep only the fully-booked event
        response["workshopEventWsDTO"] = [
            e
            for e in response["workshopEventWsDTO"]
            if e["remainingSeats"] == 0
        ]
        self.assertEqual(len(response["workshopEventWsDTO"]), 1)

        pw, ctx, resp = _build_playwright_mocks(response)
        mock_pw.return_value = pw.return_value
        mock_pw.return_value.__aenter__.return_value = (
            pw.return_value.__aenter__.return_value
        )

        self._run(run2())

        # No alerts or registration for a fully-booked workshop
        mock_slack_scraper.assert_not_called()
        mock_urgent.assert_not_called()

    @patch("service.alert.send_urgent_workshop_alert")
    @patch("scraper.home_depo.send_slack_message")
    @patch("service.alert.send_slack_message")
    @patch("scraper.home_depo.update_last_alert_date")
    @patch("scraper.home_depo.get_last_alert_date", return_value=None)
    @patch("playwright.async_api.async_playwright")
    def test_skips_non_kid_workshop(
        self,
        mock_pw,
        mock_get_date,
        mock_update_date,
        mock_slack_svc,
        mock_slack_scraper,
        mock_urgent,
        _wc,
    ):
        """A workshop with workshopType != 'KID' should be skipped."""
        response = _load_fixture("homedepot_sample_response.json")
        # Change the eligible workshop to a DIY type
        response["workshopEventWsDTO"][0]["workshopType"] = "DIY"
        # Remove the fully-booked workshop so we isolate the test
        response["workshopEventWsDTO"] = [response["workshopEventWsDTO"][0]]

        pw, ctx, resp = _build_playwright_mocks(response)
        mock_pw.return_value = pw.return_value
        mock_pw.return_value.__aenter__.return_value = (
            pw.return_value.__aenter__.return_value
        )

        self._run(run2())

        mock_slack_scraper.assert_not_called()
        mock_urgent.assert_not_called()

    @patch("service.alert.send_urgent_workshop_alert")
    @patch("scraper.home_depo.send_slack_message")
    @patch("service.alert.send_slack_message")
    @patch("scraper.home_depo.update_last_alert_date")
    @patch("scraper.home_depo.get_last_alert_date", return_value=None)
    @patch("playwright.async_api.async_playwright")
    def test_skips_inactive_workshop(
        self,
        mock_pw,
        mock_get_date,
        mock_update_date,
        mock_slack_svc,
        mock_slack_scraper,
        mock_urgent,
        _wc,
    ):
        """A workshop with workshopStatus != 'ACTIVE' should be skipped."""
        response = _load_fixture("homedepot_sample_response.json")
        response["workshopEventWsDTO"][0]["workshopStatus"] = "CLOSED"
        response["workshopEventWsDTO"] = [response["workshopEventWsDTO"][0]]

        pw, ctx, resp = _build_playwright_mocks(response)
        mock_pw.return_value = pw.return_value
        mock_pw.return_value.__aenter__.return_value = (
            pw.return_value.__aenter__.return_value
        )

        self._run(run2())

        mock_slack_scraper.assert_not_called()
        mock_urgent.assert_not_called()

    # -- error scenarios ---------------------------------------------------

    @patch("service.alert.send_api_error_alert")
    @patch("playwright.async_api.async_playwright")
    def test_api_returns_500(self, mock_pw, mock_api_alert, _wc):
        """Non-200 status → send_api_error_alert is called."""
        pw, ctx, resp = _build_playwright_mocks(
            "Internal Server Error", status=500
        )
        mock_pw.return_value = pw.return_value
        mock_pw.return_value.__aenter__.return_value = (
            pw.return_value.__aenter__.return_value
        )

        self._run(run2())

        mock_api_alert.assert_called_once()
        args = mock_api_alert.call_args[0]
        self.assertIn("500", args[2])

    @patch("service.alert.send_api_error_alert")
    @patch("playwright.async_api.async_playwright")
    def test_api_returns_empty_body(self, mock_pw, mock_api_alert, _wc):
        """Empty response body → send_api_error_alert."""
        pw, ctx, resp = _build_playwright_mocks("", status=200)
        # Make text() return empty string
        resp.text.return_value = ""
        mock_pw.return_value = pw.return_value
        mock_pw.return_value.__aenter__.return_value = (
            pw.return_value.__aenter__.return_value
        )

        self._run(run2())

        mock_api_alert.assert_called_once()
        args = mock_api_alert.call_args[0]
        self.assertIn("empty", args[1].lower())

    @patch("service.alert.send_api_error_alert")
    @patch("playwright.async_api.async_playwright")
    def test_api_returns_invalid_json(self, mock_pw, mock_api_alert, _wc):
        """Malformed JSON → JSON parsing error alert."""
        pw, ctx, resp = _build_playwright_mocks("{ not valid JSON !!!")
        mock_pw.return_value = pw.return_value
        mock_pw.return_value.__aenter__.return_value = (
            pw.return_value.__aenter__.return_value
        )

        self._run(run2())

        mock_api_alert.assert_called_once()
        args = mock_api_alert.call_args[0]
        self.assertEqual(args[1], "JSON parsing error")

    @patch("service.alert.send_api_error_alert")
    @patch("playwright.async_api.async_playwright")
    def test_api_missing_workshopEventWsDTO_key(self, mock_pw, mock_api_alert, _wc):
        """Response missing the expected key → alert about missing structure."""
        pw, ctx, resp = _build_playwright_mocks({"someOtherKey": []})
        mock_pw.return_value = pw.return_value
        mock_pw.return_value.__aenter__.return_value = (
            pw.return_value.__aenter__.return_value
        )

        self._run(run2())

        mock_api_alert.assert_called_once()
        args = mock_api_alert.call_args[0]
        self.assertIn("missing expected", args[1])

    @patch("service.alert.send_api_error_alert")
    @patch("playwright.async_api.async_playwright")
    def test_api_empty_workshop_list(self, mock_pw, mock_api_alert, _wc):
        """workshopEventWsDTO is an empty list → no processing, no error."""
        pw, ctx, resp = _build_playwright_mocks({"workshopEventWsDTO": []})
        mock_pw.return_value = pw.return_value
        mock_pw.return_value.__aenter__.return_value = (
            pw.return_value.__aenter__.return_value
        )

        self._run(run2())

        # Empty list is handled gracefully without sending an error alert
        mock_api_alert.assert_not_called()

    @patch("service.alert.send_api_error_alert")
    @patch("playwright.async_api.async_playwright")
    def test_playwright_exception(self, mock_pw, mock_api_alert, _wc):
        """Unexpected exception in Playwright → send_api_error_alert."""
        # Raise at context.get() level so it's inside the try/except in run2()
        mock_context = AsyncMock()
        mock_context.get.side_effect = Exception("Browser crashed")

        mock_pw_instance = AsyncMock()
        mock_pw_instance.request.new_context.return_value = mock_context
        mock_pw.return_value.__aenter__.return_value = mock_pw_instance

        self._run(run2())

        mock_api_alert.assert_called_once()
        args = mock_api_alert.call_args[0]
        self.assertIn("Unexpected error", args[1])

    # -- fixture integrity -------------------------------------------------

    def test_sample_response_fixture_structure(self, _wc):
        """Sanity check: the fixture has the expected shape."""
        data = self.sample_response
        self.assertIn("workshopEventWsDTO", data)
        self.assertEqual(len(data["workshopEventWsDTO"]), 2)

        first = data["workshopEventWsDTO"][0]
        self.assertEqual(first["code"], "MWBT0005")
        self.assertEqual(first["workshopType"], "KID")
        self.assertEqual(first["workshopStatus"], "ACTIVE")
        self.assertEqual(first["remainingSeats"], 19)
        self.assertIn("08:30", first["startTime"])
        self.assertEqual(first["eventType"]["name"], "Build a Leprechaun Trap")

        second = data["workshopEventWsDTO"][1]
        self.assertEqual(second["code"], "MWBT0006")
        self.assertEqual(second["remainingSeats"], 0)

    def test_registration_payload_fixture_structure(self, _wc):
        """Sanity check: the registration payload fixture is well-formed."""
        payload = _load_fixture("homedepot_registration_payload.json")
        self.assertIn("customer", payload)
        self.assertEqual(payload["customer"]["firstName"], "En")
        self.assertEqual(payload["store"], "7265")
        self.assertEqual(payload["participantCount"], 2)
        self.assertEqual(payload["workshopEventCode"], "MWBT0005")

    def test_fixture_payload_matches_response_event(self, _wc):
        """
        The registration payload's workshopEventCode should match an event
        code in the sample response, ensuring the fixtures are consistent.
        """
        payload = _load_fixture("homedepot_registration_payload.json")
        event_codes = [
            e["code"] for e in self.sample_response["workshopEventWsDTO"]
        ]
        self.assertIn(payload["workshopEventCode"], event_codes)


if __name__ == "__main__":
    unittest.main()
