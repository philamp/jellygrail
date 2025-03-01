import websocket
import json
import threading

# toremove later

is_scanning = True

kodi_ws_url = f"ws://172.22.2.14:9090/jsonrpc"

def on_message(ws, message):
    global is_scanning
    data = json.loads(message)

    # Look for the scan start and finish events
    if "method" in data:
        if data["method"] == "VideoLibrary.OnScanFinished":
            print("message received : scan finisehd")
            is_scanning = False
        if data["method"] == "VideoLibrary.OnScanStarted":
            print("message received : scan started")

def on_error(ws, error):
    global is_scanning
    print(f"!! WebSocket error: {error}, please enable 'Allow remote control from applications on other systems' via Kodi UI in Settings/Services/Control [kodi_services]")
    is_scanning = False 

def on_close(ws, close_status_code, close_msg):
    print("> WebSocket connection closed. [kodi_services]")

def on_open(ws):
    print("~ WebSocket waiting for Kodi scan to be finished [kodi_services] ~")

if __name__ == "__main__":
    ws = websocket.WebSocketApp(kodi_ws_url,
                                on_message=on_message,
                                on_error=on_error,
                                on_open=on_open,
                                on_close=on_close)

    # Run the WebSocket in a separate thread to allow for graceful shutdown
    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = False
    wst.start()