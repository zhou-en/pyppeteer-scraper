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
                initial_comment="Here is a screenshot when the item is available!"
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


def send_email_with_attachment(sender_email, sender_name, sender_password,
                               recipients, subject, body, attachment_path):
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
