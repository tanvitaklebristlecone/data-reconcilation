from API_conn.connectors.base_connector import SAPConnector
from API_conn.config.config_loader import load_config
import pandas as pd
import requests


class IBPDemandConnector(SAPConnector):

    def __init__(self):
        config = load_config()["ibp"]
        super().__init__(config)

    def fetch(self):

        endpoint = (
            self.config["base_url"]
            + self.config["service"]
        )

        print("\nEndpoint:")
        print(endpoint)

        response = requests.get(
            endpoint,
            auth=(
                self.config["username"],
                self.config["password"]
            ),
            headers={
                "Accept": "application/json"
            },
            timeout=60,
            allow_redirects=False
        )

        print("\nStatus Code:")
        print(response.status_code)

        print("\nHeaders:")
        print(response.headers)

        print("\nResponse Preview:")
        print(response.text[:3000])

        response.raise_for_status()

        return pd.DataFrame()