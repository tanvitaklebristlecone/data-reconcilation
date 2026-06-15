from API_conn.connectors.ibp_connector import IBPDemandConnector

connector = IBPDemandConnector()

df = connector.fetch()

print(df.head())
print(df.shape)