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
            text=message
        )

        # Check if the message was sent successfully
        if response['ok']:
            print("Message sent to Slack successfully.")
        else:
            print("Failed to send message to Slack.")
    except SlackApiError as e:
        print(f"Error sending message to Slack: {e.response['error']}")
