from API_conn.connectors.base_connector import SAPConnector
import pandas as pd

class S4SalesOrderConnector(SAPConnector):

    def fetch(self):
        """
        Future:
        GET API_SALES_ORDER_SRV
        """

        return pd.DataFrame()
    

"""
s4:
  base_url: https://<s4-host>
  service: API_SALES_ORDER_SRV
  username: <user>
  password: <password>

Base URL
Authentication type
Username
Password
Client number
API_SALES_ORDER_SRV endpoint

"""