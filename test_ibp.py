from API_conn.connectors.ibp_connector import IBPDemandConnector

connector = IBPDemandConnector()

try:
    df = connector.fetch()

    print("SUCCESS")
    print(df.head())
    print(df.shape)

except Exception as e:
    print("ERROR")
    print(e)