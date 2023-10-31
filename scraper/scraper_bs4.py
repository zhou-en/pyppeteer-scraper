import os
import requests


API_KEY = os.environ.get("API_KEY") 

response = requests.get(
    url='https://proxy.scrapeops.io/v1/',
    params={
        'api_key': API_KEY,
        'url': 'https://quotes.toscrape.com/',
    },
)

print('Response Body: ', response.content)
