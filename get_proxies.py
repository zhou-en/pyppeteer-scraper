"""
Create a list of free proxy ip and port and save in a JSON file.
"""

import requests


def get_proxies():
    proxy_url = "https://proxylist.geonode.com/api/proxy-list?limit=50&page=1&sort_by=lastChecked&speed=fast"
    response = requests.get(proxy_url)
    with open("proxies.json", "wb") as f:
        f.write(response.content)


if __name__ == '__main__':
    get_proxies()
