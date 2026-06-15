from base_connector import SAPConnector
import pandas as pd

class IBPDemandConnector(SAPConnector):

    def fetch(self):
        """
        Future:
        GET /IBP/PLANNING_DATA_API_SRV
        """

        return pd.DataFrame()

"""
ibp:
  base_url: https://<ibp-host>
  service: /IBP/PLANNING_DATA_API_SRV
  username: <user>
  password: <password>

Tenant URL
Authentication method
Planning Area
Key Figure name
Planning level
/IBP/PLANNING_DATA_API_SRV endpoint

"""