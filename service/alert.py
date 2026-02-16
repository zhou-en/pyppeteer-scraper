import datetime
import json
import logging
import os
import smtplib
import sys
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv
from slack import WebClient
from slack.errors import SlackApiError

logging.basicConfig(
    filename="app.log", filemode="w", format="%(name)s - %(levelname)s - %(message)s"
)

load_dotenv()

# Your Slack API token
slack_token = os.environ.get("SLACK_API_TOKEN")
channel_id = os.environ.get("CHANNEL_ID")
if not (slack_token and channel_id):
    logging.error("No Slack token or channel ID found.")
    sys.exit(1)

# Initialize the Slack API client
client = WebClient(token=slack_token)


def get_owner_id():
    """
    Gets the channel owner ID and tag it in the message
    :return:
    """
    response = client.users_list()
    users = response["members"]
    logging.info(f"Getting all users: {users}")
    for user in users:
        logging.info(f"User: {user['real_name']}, ID: {user['id']}")
        if user.get("is_owner"):
            return user.get("id")


def send_slack_message(message, screenshot_path=None):
    try:
        # Send the message to Slack
        user_id = get_owner_id()
        message = f"<@{user_id}>, {message}"

        # Compose the message blocks
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message,
                },
            }
        ]

        response = client.chat_postMessage(channel=channel_id, blocks=blocks)

        # Check if the message was sent successfully
        if response["ok"]:
            logging.info("Message sent to Slack successfully.")
        else:
            logging.info("Failed to send message to Slack.")

        # Upload the screenshot if provided
        if screenshot_path:
            logging.info(f"Start uploading screenshot: {screenshot_path}")
            response = client.files_upload(
                channels=channel_id,
                file=screenshot_path,
                title="Here is a screenshot when the item is available",
                initial_comment="Here is a screenshot when the item is available!",
            )
            logging.info(f"Uploaded screenshot: {response}")
            if response["ok"]:
                logging.info("Screenshot sent to Slack successfully.")
            else:
                logging.info("Failed to send screenshot to Slack.")

    except SlackApiError as e:
        logging.error(f"Error sending message to Slack: {e}")


def get_last_alert_date(scraper_name: str):
    """
    Read the last alert sent by a scraper from storage/last_alert.json
    :return:
    """
    file_path = "storage/last_alert.json"
    if os.path.getsize(file_path) == 0:
        return None

    with open(file_path, "r") as f:
        last_alert_data = json.load(f)
    last_date = last_alert_data.get(scraper_name, None)
    if not last_date:
        return None
    return datetime.datetime.strptime(last_date, "%Y-%m-%d").date()


def update_last_alert_date(scraper_name: str, new_date: datetime.date):
    """
    Update
    :param new_date:
    :param scraper_name:
    :return:
    """
    date_str = new_date.strftime("%Y-%m-%d")
    file_path = "storage/last_alert.json"
    # empty file
    if os.path.getsize(file_path) == 0:
        last_alert_data = {scraper_name: date_str}
        with open("storage/last_alert.json", "w") as f:
            json.dump(last_alert_data, f)
    else:
        # read exiting content
        with open("storage/last_alert.json", "r") as f:
            last_alert_data = json.load(f)
        # update with new data
        last_alert_data.update({scraper_name: date_str})
        # write new content
        with open("storage/last_alert.json", "w") as f:
            json.dump(last_alert_data, f)


def send_email_with_attachment(
    sender_email,
    sender_name,
    sender_password,
    recipients,
    subject,
    body,
    attachment_path,
):
    """
    Sends an email with an attachment to multiple recipients.

    Parameters:
    - sender_email (str): Sender's email address.
    - sender_name (str): Sender's display name.
    - sender_password (str): Sender's email password.
    - recipients (list): List of recipient email addresses.
    - subject (str): Email subject.
    - body (str): Email body content.
    - attachment_path (str): Path to the attachment file.
    - smtp_server (str): SMTP server address.
    - smtp_port (int): SMTP server port.
    """
    # Create email message
    msg = MIMEMultipart()
    msg["From"] = sender_name + " <" + sender_email + ">"
    msg["To"] = recipients
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # Attach the file
    try:
        with open(attachment_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename= {attachment_path.split('/')[-1]}",
            )
            msg.attach(part)
    except FileNotFoundError:
        print(f"Attachment file not found: {attachment_path}")
        return

    # Send the email
    smtp_server = os.environ.get("SMTP_SERVER", "")
    smtp_port = os.environ.get("SMTP_PORT", 465)
    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipients, msg.as_string())
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")


def send_urgent_workshop_alert(workshop_details, registration_url=None):
    """
    Send an urgent, high-visibility alert for time-sensitive workshop openings
    with direct registration links to enable fast manual action if needed.

    Args:
        workshop_details: Dict with workshop info (title, date, event_code, seats_left)
        registration_url: Direct URL for registration if available
    """
    try:
        user_id = get_owner_id()

        # If no direct registration URL provided, use the general workshops page
        if not registration_url:
            registration_url = "https://www.homedepot.ca/workshops?store=7265"

        # Create an urgent-looking message with visual indicators
        title = workshop_details.get("title", "Unknown Workshop")
        date = workshop_details.get("date", "Unknown Date")
        event_code = workshop_details.get("event_code", "Unknown Code")
        seats_left = workshop_details.get("seats_left", "Unknown")

        # Construct a message with high visibility and all the info needed to act quickly
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔴 URGENT: WORKSHOP REGISTRATION OPEN 🔴",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{user_id}> *Workshop available for registration!*",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Workshop:*\n{title}"},
                    {"type": "mrkdwn", "text": f"*Date:*\n{date}"},
                    {"type": "mrkdwn", "text": f"*Event Code:*\n`{event_code}`"},
                    {"type": "mrkdwn", "text": f"*Seats Left:*\n{seats_left}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*⚠️ Limited time to register! Act quickly! ⚠️*",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "🔗 Register Now",
                            "emoji": True,
                        },
                        "style": "primary",
                        "url": registration_url,
                    }
                ],
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"⏰ Alert sent at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    }
                ],
            },
        ]

        # Send the message with the special formatting
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"URGENT: {title} workshop is open for registration!",
            # Fallback text
        )

        # If we want to make the message extra noticeable, pin it to the channel
        if response["ok"]:
            try:
                # Pin the message to the channel
                client.pins_add(channel=channel_id, timestamp=response["ts"])
                logging.info("Urgent workshop alert pinned to channel")
            except SlackApiError as e:
                logging.error(f"Error pinning urgent message: {e}")

            # Send a follow-up @channel message to trigger notifications for everyone
            try:
                client.chat_postMessage(
                    channel=channel_id,
                    text=f"<!channel> A new workshop '{title}' is available for registration!",
                )
            except SlackApiError as e:
                logging.error(f"Error sending @channel notification: {e}")

            logging.info(f"Urgent workshop alert sent for {title}")
            return True
        else:
            logging.error("Failed to send urgent workshop alert")
            return False
    except Exception as e:
        logging.error(f"Error sending urgent workshop alert: {str(e)}")
        return False


def send_api_error_alert(service_name, error_message, details=None):
    """
    Send an error alert about API failures to Slack
    Args:
        service_name: Name of the service with API issue (e.g., 'Home Depot API')
        error_message: Brief description of the error
        details: Additional details/context about the error (optional)
    """
    try:
        # Create a more visible error message with emoji and formatting
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🚨 *API ERROR - {service_name}* 🚨\n{error_message}",
                },
            }
        ]

        # Add error details if provided
        if details:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Details:*\n```{details}```"},
                }
            )

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"⏰ Error occurred at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    }
                ],
            }
        )

        # Send the message to Slack
        client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"API ERROR - {service_name}: {error_message}",  # Fallback text
        )
        logging.info(f"API error alert sent to Slack: {error_message}")
        return True
    except SlackApiError as e:
        logging.error(f"Error sending API error alert to Slack: {e.response['error']}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error sending API error alert: {str(e)}")
        return False


def get_registered_workshops(scraper_name: str):
    """
    Read the list of workshops that have been successfully registered for
    from storage/registered_workshops.json

    Args:
        scraper_name: Name of the scraper (e.g., "home_depo")

    Returns:
        dict: Dictionary mapping workshop_event_ids to registration details
              Returns empty dict if no registrations found
    """
    file_path = "storage/registered_workshops.json"

    # Create storage directory if it doesn't exist
    os.makedirs("storage", exist_ok=True)

    # Create empty file if it doesn't exist
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            json.dump({}, f)
        return {}

    # Handle empty file
    if os.path.getsize(file_path) == 0:
        return {}

    with open(file_path, "r") as f:
        all_registrations = json.load(f)

    return all_registrations.get(scraper_name, {})


def is_workshop_registered(scraper_name: str, workshop_event_id: str):
    """
    Check if a specific workshop has already been registered for

    Args:
        scraper_name: Name of the scraper (e.g., "home_depo")
        workshop_event_id: The workshop event ID (e.g., "WS00029")

    Returns:
        bool: True if workshop is already registered, False otherwise
    """
    registered_workshops = get_registered_workshops(scraper_name)
    workshop_info = registered_workshops.get(workshop_event_id)
    
    if not workshop_info:
        return False
        
    # specific check for boolean, defaulting to True for backward compatibility
    return workshop_info.get("is_registered", True)


def save_registered_workshop(
    scraper_name: str,
    workshop_event_id: str,
    workshop_id: str,
    title: str,
    event_date: str,
    registration_date: datetime.datetime = None,
    is_registered: bool = True,
):
    """
    Save a successful workshop registration to storage

    Args:
        scraper_name: Name of the scraper (e.g., "home_depo")
        workshop_event_id: The workshop event ID (e.g., "WS00029")
        workshop_id: The specific workshop instance ID (e.g., "KWBE0001")
        title: Workshop title
        event_date: Date of the workshop event
        registration_date: When the registration was made (defaults to now)
        is_registered: Boolean flag indicating if the workshop is fully registered
    """
    if registration_date is None:
        registration_date = datetime.datetime.now()

    registration_info = {
        "workshop_id": workshop_id,
        "workshop_event_id": workshop_event_id,
        "title": title,
        "event_date": event_date,
        "registration_date": registration_date.strftime("%Y-%m-%d %H:%M:%S"),
        "is_registered": is_registered,
    }

    file_path = "storage/registered_workshops.json"

    # Create storage directory if it doesn't exist
    os.makedirs("storage", exist_ok=True)

    # Load existing data or start fresh
    all_registrations = {}
    if os.path.exists(file_path):
        try:
            if os.path.getsize(file_path) > 0:
                with open(file_path, "r") as f:
                    all_registrations = json.load(f)
        except json.JSONDecodeError:
            pass  # Start fresh if file is corrupted

    # Initialize scraper's registrations if not present
    if scraper_name not in all_registrations:
        all_registrations[scraper_name] = {}

    # Save the registration
    # If it already exists, we are updating it (e.g. from discovered to registered)
    all_registrations[scraper_name][workshop_event_id] = registration_info

    # Write updated data
    with open(file_path, "w") as f:
        json.dump(all_registrations, f, indent=2)

    status = "registered" if is_registered else "discovered"
    logging.info(f"Saved {status} workshop {workshop_event_id} ({title})")
