import requests

API_KEY = "93c41243-ded3-49de-a08e-ce24749e78dd"

response = requests.get(
    url='https://proxy.scrapeops.io/v1/',
    params={
        'api_key': API_KEY,
        'url': 'https://quotes.toscrape.com/',
    },
)

print('Response Body: ', response.content)
