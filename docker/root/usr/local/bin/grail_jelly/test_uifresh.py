import requests
import json

# Kodi connection details
KODI_IP = 'http://172.22.2.14:8080/jsonrpc'
USERNAME = 'kodi'
PASSWORD = 'kodi'

# The path to the folder you want to refresh
folder_path = 'dummy/path/just/to/refresh'

# Create the JSON-RPC request
payload = {
    "jsonrpc": "2.0",
    "method": "VideoLibrary.Scan",
    "params": {"directory": folder_path},
    "id": "1"
}

# Send the request
response = requests.post(KODI_IP, data=json.dumps(payload), auth=(USERNAME, PASSWORD))

# Print the response
print(response.json())