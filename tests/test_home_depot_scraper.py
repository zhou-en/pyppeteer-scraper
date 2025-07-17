import asyncio
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import requests

# Add parent directory to path to allow imports
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

# Import the module to test
from scraper.home_depo import register_home_depot_workshop, run2


# Mock the entire slack WebClient class at module level
# This prevents any actual Slack API calls during testing
@patch('slack.WebClient')
class TestHomeDepotScraper(unittest.TestCase):
    """
    Test suite for the Home Depot scraper functionality
    """

    def setUp(self):
        """Set up test fixtures"""
        # Create a sample workshop event response
        self.sample_workshop_response = {
            "workshopEventWsDTO": [
                {
                    "code": "KWTM12345",
                    "workshopType": "KID",
                    "remainingSeats": 5,
                    "workshopStatus": "ACTIVE",
                    "eventDate": "2023-12-31T14:00:00Z",
                    "eventType": {
                        "name": "Test Kid Workshop"
                    }
                },
                {
                    "code": "ADULT12345",
                    "workshopType": "ADULT",
                    "remainingSeats": 10,
                    "workshopStatus": "ACTIVE",
                    "eventDate": "2023-12-31T16:00:00Z",
                    "eventType": {
                        "name": "Test Adult Workshop"
                    }
                },
                {
                    "code": "KWTM67890",
                    "workshopType": "KID",
                    "remainingSeats": 0,
                    "workshopStatus": "ACTIVE",
                    "eventDate": "2023-12-31T15:00:00Z",
                    "eventType": {
                        "name": "Full Kid Workshop"
                    }
                },
                {
                    "code": "KWTM54321",
                    "workshopType": "KID",
                    "remainingSeats": 3,
                    "workshopStatus": "INACTIVE",
                    "eventDate": "2023-12-31T17:00:00Z",
                    "eventType": {
                        "name": "Inactive Kid Workshop"
                    }
                }
            ]
        }

        # Sample registration success response
        self.sample_registration_success = {
            "success": True,
            "message": "Registration successful"
        }

        # Sample registration failure response
        self.sample_registration_failure = {
            "success": False,
            "message": "Registration failed - workshop is full"
        }

    # Fix 1: Correcting the mock paths to 'service.alert' instead of 'scraper.home_depo'
    @patch('service.alert.send_slack_message')
    @patch('service.alert.send_api_error_alert')
    @patch('requests.post')
    def test_register_workshop_success(self, mock_post, mock_api_alert, mock_slack, mock_webclient):
        """Test successful workshop registration"""
        # Configure the mock
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_registration_success
        mock_response.text = json.dumps(self.sample_registration_success)
        mock_post.return_value = mock_response

        event_code = "KWTM12345"

        # Call the function
        success, response = register_home_depot_workshop(
            event_code,
            first_name="Test",
            last_name="User",
            email="test@example.com",
            store_id="7265",
            participant_count=2
        )

        # Assertions
        self.assertTrue(success)
        mock_post.assert_called_once()
        mock_api_alert.assert_called_once()

        # Check that the request was made with the correct parameters
        call_args = mock_post.call_args
        url = call_args[0][0] if len(call_args[0]) > 0 else call_args[1].get('url')
        self.assertIn(event_code, url, f"URL should contain event code {event_code}, but was {url}")

        # Check that the payload contains the correct information
        json_data = call_args[1].get('json', {})
        self.assertEqual(json_data.get('customer', {}).get('firstName'), "Test")

    @patch('service.alert.send_slack_message')
    @patch('service.alert.send_api_error_alert')
    @patch('requests.post')
    def test_register_workshop_failure(self, mock_post, mock_api_alert, mock_slack, mock_webclient):
        """Test failed workshop registration"""
        # Configure the mock
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.json.return_value = self.sample_registration_failure
        mock_response.text = json.dumps(self.sample_registration_failure)
        mock_post.return_value = mock_response

        # Call the function
        success, response = register_home_depot_workshop(
            "KWTM12345",
            first_name="Test",
            last_name="User",
            email="test@example.com"
        )

        # Assertions
        self.assertFalse(success)
        mock_post.assert_called_once()
        mock_api_alert.assert_called_once()

        # Verify the error alert had the right parameters
        args, kwargs = mock_api_alert.call_args
        self.assertIn("failed", args[1])

    @patch('service.alert.send_slack_message')
    @patch('service.alert.send_api_error_alert')
    @patch('requests.post')
    def test_register_workshop_exception(self, mock_post, mock_api_alert, mock_slack, mock_webclient):
        """Test exception handling in workshop registration"""
        # Configure the mock to raise an exception
        mock_post.side_effect = requests.exceptions.RequestException("Network error")

        # Call the function
        success, response = register_home_depot_workshop("KWTM12345")

        # Assertions
        self.assertFalse(success)
        mock_post.assert_called_once()
        mock_api_alert.assert_called_once()

        # Verify the error alert had the right parameters
        args, kwargs = mock_api_alert.call_args
        self.assertIn("error", args[1].lower())

    # Fix 2: Using a proper async test method that correctly awaits coroutines
    @patch('scraper.home_depo.register_home_depot_workshop')
    @patch('service.alert.send_urgent_workshop_alert')
    @patch('scraper.home_depo.send_slack_message')
    @patch('service.alert.send_slack_message')
    @patch('scraper.home_depo.update_last_alert_date')
    @patch('scraper.home_depo.get_last_alert_date')
    @patch('service.alert.send_api_error_alert')      # Only patch at source
    @patch('playwright.async_api.async_playwright')
    def test_run2_workshop_processing(self, mock_playwright, mock_api_alert_source,
                                     mock_get_date, mock_update_date,
                                     mock_slack_source, mock_slack_imported, mock_urgent,
                                     mock_register, mock_webclient):
        """Test the main run2 function's workshop processing logic"""
        # Set up mocks
        mock_get_date.return_value = None  # No previous alert
        mock_register.return_value = (True, "Success")
        mock_slack_imported.return_value = True
        mock_slack_source.return_value = True
        mock_urgent.return_value = True
        mock_api_alert_source.return_value = True

        # Use the real Home Depot API response format but modify it slightly
        # to work with our improved date parsing
        home_depot_response = {
            "dihFlag": False,
            "diyFlag": True,
            "kidFlag": True,
            "workshopEventWsDTO": [
                {
                    "code": "KWSO0001",
                    "workshopId": "KWSO0001",
                    "attendeeLimit": 96,
                    "duration": "1.5",
                    "closeDate": "2025-08-03T23:59:59-04:00",  # Fixed format
                    "endTime": "2025-08-09T10:00:00-04:00",    # Fixed format
                    "eventDate": "2025-08-09T08:30:00-04:00",  # Fixed format
                    "startTime": "2025-08-09T08:30:00-04:00",  # Fixed format
                    "workshopStatus": "ACTIVE",
                    "workshopType": "KID",
                    "remainingSeats": 5,
                    "eventType": {
                        "workshopEventId": "WS00025",
                        "code": "WS00025",
                        "name": "Build a Space Odyssey",
                        "shortCode": "KWSO"
                    }
                }
            ]
        }

        # Create mock context and response
        mock_context = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text.return_value = json.dumps(home_depot_response)
        mock_response.json.return_value = home_depot_response

        # Configure playwright mock
        mock_playwright_instance = AsyncMock()
        mock_playwright_instance.request.new_context.return_value = mock_context
        mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
        mock_context.get.return_value = mock_response

        # Run the async function with asyncio
        asyncio.run(run2())

        # Assertions
        mock_context.get.assert_called_once()

        # Should find the active kid workshop with available seats and send alerts
        # Check that any version of slack_message was called
        self.assertTrue(mock_slack_imported.called or mock_slack_source.called)

        # Check other expected function calls
        mock_urgent.assert_called()
        mock_update_date.assert_called()

        # Should attempt to register for workshops that start with KWSO
        # Our test data has code "KWSO0001" which doesn't match the KWTM pattern,
        # so registration shouldn't be called
        mock_register.assert_not_called()

    @patch('service.alert.send_api_error_alert')
    @patch('playwright.async_api.async_playwright')
    def test_run2_api_error(self, mock_playwright, mock_api_alert, mock_webclient):
        """Test handling of API errors in run2"""
        # Create mock context and error response
        mock_context = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.text.return_value = "Internal Server Error"

        # Configure playwright mock
        mock_playwright_instance = AsyncMock()
        mock_playwright_instance.request.new_context.return_value = mock_context
        mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
        mock_context.get.return_value = mock_response

        # Run the async function with asyncio
        asyncio.run(run2())

        # Assertions
        mock_api_alert.assert_called_once()
        args, kwargs = mock_api_alert.call_args
        self.assertIn("500", args[2])  # Error details should mention status code

    @patch('service.alert.send_api_error_alert')
    @patch('playwright.async_api.async_playwright')
    def test_run2_json_parse_error(self, mock_playwright, mock_api_alert, mock_webclient):
        """Test handling of JSON parsing errors"""
        # Create mock context and invalid JSON response
        mock_context = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text.return_value = "{ invalid json }"
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "{ invalid json }", 0)

        # Configure playwright mock
        mock_playwright_instance = AsyncMock()
        mock_playwright_instance.request.new_context.return_value = mock_context
        mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
        mock_context.get.return_value = mock_response

        # Run the async function with asyncio
        asyncio.run(run2())

        # Assertions
        mock_api_alert.assert_called_once()
        args, kwargs = mock_api_alert.call_args
        self.assertEqual(args[1], "JSON parsing error")

    @patch('service.alert.send_api_error_alert')
    @patch('playwright.async_api.async_playwright')
    def test_run2_missing_data_structure(self, mock_playwright, mock_api_alert, mock_webclient):
        """Test handling of missing expected data structure"""
        # Create mock context and response with missing key
        mock_context = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}

        # Response is missing the expected workshopEventWsDTO key
        invalid_response = {"someOtherKey": []}
        mock_response.text.return_value = json.dumps(invalid_response)
        mock_response.json.return_value = invalid_response

        # Configure playwright mock
        mock_playwright_instance = AsyncMock()
        mock_playwright_instance.request.new_context.return_value = mock_context
        mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
        mock_context.get.return_value = mock_response

        # Run the async function with asyncio
        asyncio.run(run2())

        # Assertions
        mock_api_alert.assert_called_once()
        args, kwargs = mock_api_alert.call_args
        self.assertIn("missing expected", args[1])


# Fix 3: Add a custom test runner that can handle async tests properly
def run_async_test(test_case):
    """Helper function to run an async test case"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(test_case)
    finally:
        loop.close()


if __name__ == "__main__":
    unittest.main()
