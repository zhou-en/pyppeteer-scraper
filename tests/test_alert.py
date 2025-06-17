import json
import os
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock, mock_open, patch

# Add parent directory to path to import service.alert
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from service.alert import (
    get_owner_id,
    send_slack_message,
    get_last_alert_date,
    update_last_alert_date,
    send_email_with_attachment,
)


class TestSlackMessage(unittest.TestCase):
    @patch('service.alert.client.chat_postMessage')
    @patch('service.alert.get_owner_id')
    def test_send_slack_message_success(self, mock_get_owner, mock_post_message):
        # Setup mocks
        mock_get_owner.return_value = 'U12345678'
        mock_post_message.return_value = {"ok": True}

        # Call function
        send_slack_message("Test message")

        # Assert the message was sent with the right owner ID
        mock_post_message.assert_called_once()

        # Extract and verify the call arguments
        args, kwargs = mock_post_message.call_args
        self.assertEqual(kwargs["channel"], os.environ.get("CHANNEL_ID"))
        self.assertTrue(len(kwargs["blocks"]) > 0)
        self.assertIn("<@U12345678>", kwargs["blocks"][0]["text"]["text"])
        self.assertIn("Test message", kwargs["blocks"][0]["text"]["text"])

    @patch('service.alert.client.chat_postMessage')
    @patch('service.alert.client.files_upload')
    @patch('service.alert.get_owner_id')
    def test_send_slack_message_with_screenshot(self, mock_get_owner, mock_files_upload, mock_post_message):
        # Setup mocks
        mock_get_owner.return_value = 'U12345678'
        mock_post_message.return_value = {"ok": True}
        mock_files_upload.return_value = {"ok": True}

        # Call function with screenshot path
        screenshot_path = "test_screenshot.png"
        send_slack_message("Test message", screenshot_path)

        # Assert the message was sent
        mock_post_message.assert_called_once()

        # Assert screenshot was uploaded
        mock_files_upload.assert_called_once()
        args, kwargs = mock_files_upload.call_args
        self.assertEqual(kwargs["channels"], os.environ.get("CHANNEL_ID"))
        self.assertEqual(kwargs["file"], screenshot_path)

    @patch('service.alert.client.chat_postMessage')
    @patch('service.alert.get_owner_id')
    @patch('service.alert.logging')
    def test_send_slack_message_failure(self, mock_logging, mock_get_owner, mock_post_message):
        # Setup mocks
        mock_get_owner.return_value = 'U12345678'
        mock_post_message.return_value = {"ok": False}

        # Call function
        send_slack_message("Test message")

        # Check logging of failure
        mock_logging.info.assert_any_call("Failed to send message to Slack.")

    @patch('service.alert.client')
    @patch('service.alert.logging')
    def test_get_owner_id(self, mock_logging, mock_client):
        # Mock the response from Slack API
        mock_response = {
            "members": [
                {"real_name": "User 1", "id": "U123", "is_owner": False},
                {"real_name": "User 2", "id": "U456", "is_owner": True},
                {"real_name": "User 3", "id": "U789", "is_owner": False}
            ]
        }
        mock_client.users_list.return_value = mock_response

        # Call the function
        result = get_owner_id()

        # Assertions
        self.assertEqual(result, "U456")
        mock_client.users_list.assert_called_once()


class TestAlertDate(unittest.TestCase):
    def setUp(self):
        # Create test directory and file
        os.makedirs("storage", exist_ok=True)
        self.test_file = "storage/last_alert.json"

        # Clear or create the test file
        with open(self.test_file, "w") as f:
            json.dump({}, f)

    def tearDown(self):
        # Remove test file if it exists
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_get_last_alert_date_empty_file(self):
        # Create empty file
        with open(self.test_file, "w") as f:
            f.write("")

        # Get date from empty file
        result = get_last_alert_date("test_scraper")
        self.assertIsNone(result)

    def test_get_last_alert_date_missing_scraper(self):
        # Set up file with other scrapers
        with open(self.test_file, "w") as f:
            json.dump({"other_scraper": "2025-06-15"}, f)

        # Get date for non-existent scraper
        result = get_last_alert_date("test_scraper")
        self.assertIsNone(result)

    def test_get_last_alert_date_existing_scraper(self):
        # Create file with test scraper
        with open(self.test_file, "w") as f:
            json.dump({"test_scraper": "2025-06-15"}, f)

        # Get date for test scraper
        result = get_last_alert_date("test_scraper")
        self.assertEqual(result, date(2025, 6, 15))

    def test_update_last_alert_date_new_scraper(self):
        # Create empty JSON file
        with open(self.test_file, "w") as f:
            json.dump({}, f)

        # Update date for new scraper
        test_date = date(2025, 6, 16)
        update_last_alert_date("test_scraper", test_date)

        # Verify file was updated
        with open(self.test_file, "r") as f:
            data = json.load(f)
            self.assertIn("test_scraper", data)
            self.assertEqual(data["test_scraper"], "2025-06-16")

    def test_update_last_alert_date_existing_scraper(self):
        # Create file with test scraper
        with open(self.test_file, "w") as f:
            json.dump({"test_scraper": "2025-06-15", "other_scraper": "2025-06-10"}, f)

        # Update date for existing scraper
        test_date = date(2025, 6, 16)
        update_last_alert_date("test_scraper", test_date)

        # Verify file was updated
        with open(self.test_file, "r") as f:
            data = json.load(f)
            self.assertIn("test_scraper", data)
            self.assertEqual(data["test_scraper"], "2025-06-16")
            # Make sure other scraper wasn't modified
            self.assertEqual(data["other_scraper"], "2025-06-10")

    def test_update_last_alert_date_empty_file(self):
        # Create empty file (not JSON)
        with open(self.test_file, "w") as f:
            f.write("")

        # Update date for new scraper
        test_date = date(2025, 6, 16)
        update_last_alert_date("test_scraper", test_date)

        # Verify file was created with proper JSON
        with open(self.test_file, "r") as f:
            data = json.load(f)
            self.assertIn("test_scraper", data)
            self.assertEqual(data["test_scraper"], "2025-06-16")


class TestEmailService(unittest.TestCase):
    @patch('service.alert.smtplib.SMTP_SSL')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test file content')
    @patch('service.alert.os.environ.get')
    @patch('builtins.print')
    def test_send_email_with_attachment_success(self, mock_print, mock_env_get, mock_file, mock_smtp_ssl):
        # Setup environment variables
        mock_env_get.side_effect = lambda key, default=None: {
            "SMTP_SERVER": "smtp.example.com",
            "SMTP_PORT": 465
        }.get(key, default)

        # Setup SMTP mock
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        # Call the function
        send_email_with_attachment(
            "sender@example.com",
            "Sender Name",
            "password123",
            "recipient@example.com",
            "Test Subject",
            "Test Body",
            "path/to/attachment.txt"
        )

        # Assertions
        mock_server.login.assert_called_once_with("sender@example.com", "password123")
        mock_server.sendmail.assert_called_once()
        mock_print.assert_called_with("Email sent successfully!")

    @patch('service.alert.smtplib.SMTP_SSL')
    @patch('builtins.open')
    @patch('builtins.print')
    def test_send_email_attachment_not_found(self, mock_print, mock_open, mock_smtp_ssl):
        # Mock the file not found error
        mock_open.side_effect = FileNotFoundError()

        # Call the function
        send_email_with_attachment(
            "sender@example.com",
            "Sender Name",
            "password123",
            "recipient@example.com",
            "Test Subject",
            "Test Body",
            "nonexistent/file.txt"
        )

        # Assertions
        mock_print.assert_called_with("Attachment file not found: nonexistent/file.txt")
        mock_smtp_ssl.assert_not_called()


if __name__ == '__main__':
    unittest.main()
