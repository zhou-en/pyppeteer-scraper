import datetime
import json
import logging
import os
import sys

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


def send_slack_message(message):
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
