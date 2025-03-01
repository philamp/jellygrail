import requests
import json

# Kodi connection details
KODI_IP = 'http://172.22.2.14:8080/jsonrpc'
USERNAME = 'kodi'
PASSWORD = 'kodi'

# The path to the folder you want to refresh
#folder_path = 'dummy/path/just/to/refresh'

# Create the JSON-RPC request
refresh_payload = json.dumps({
    "jsonrpc": "2.0",
    "method": f"VideoLibrary.RefreshMovie",
    "params": {
        "movieid": 12001
    },
    "id": "1"
})

# Send the request
response = requests.post(KODI_IP, data=refresh_payload, auth=(USERNAME, PASSWORD))

resjson = response.json()

if resjson.get('result') != None:
    print("kodi understood the request")
else:
    print("kodi failed the request")

# Print the response
print(response.json())

print(response.status_code)