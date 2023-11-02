import datetime
import json
import os

from slack import WebClient
from slack.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()

# Your Slack API token
slack_token = os.environ.get('SLACK_API_TOKEN')
channel_id = os.environ.get('CHANNEL_ID')

# Initialize the Slack API client
client = WebClient(token=slack_token)


def send_slack_message(message):
    load_dotenv()
    try:
        # Send the message to Slack
        response = client.chat_postMessage(
            channel=channel_id,
            text=message,
            link_names=1
        )

        # Check if the message was sent successfully
        if response['ok']:
            print("Message sent to Slack successfully.")
        else:
            print("Failed to send message to Slack.")
    except SlackApiError as e:
        print(f"Error sending message to Slack: {e.response['error']}")


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
    if os.path.getsize(file_path) == 0:
        last_alert_data = {
            scraper_name: date_str
        }
        with open("storage/last_alert.json", "w") as f:
            json.dump(last_alert_data, f)
    else:
        with open("storage/last_alert.json", "w") as f:
            last_alert_data = json.load(f)
            last_alert_data.update({
                scraper_name, date_str
            })
            json.dump(last_alert_data, f)
