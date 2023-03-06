"""
Create a list of free proxy ip and port and save in a JSON file.
"""

import json
import random

import requests


class Proxy:
    def __init__(self, *args, **kwargs):
        self.path = "proxy/proxy.json"
        self.proxy_url = "https://proxylist.geonode.com/api/proxy-list?limit=50&page=1&sort_by=lastChecked&speed=fast"
        super(Proxy, self).__init__(*args, **kwargs)

    def refresh(self) -> None:
        """
        Get list of proxies from Geonode site and write to the proxy file.
        :return:
        """
        response = requests.get(self.proxy_url)
        with open(self.path, "wb") as f:
            f.write(response.content)

    def random(self) -> dict:
        """
        Return a random proxy from the proxy list
        :return:
        """
        proxy_data = self.load()
        return random.choice(proxy_data)

    def load(self) -> list:
        """
        Load the list of proxies from the proxy file
        :return:
        """
        try:
            with open(self.path, "r") as f:
                proxy_data = json.load(f)
                return proxy_data.get("data", [])
        except Exception as err:
            print(err)
            return []

    def get(self):
        """
        Returns the first proxy from the list
        :return:
        """
        proxy_data = self.load()

        if len(proxy_data) > 1:
            return proxy_data[0]
        return {}
