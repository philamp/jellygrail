#!/usr/bin/env python3
"""
listen_kodi_ws.py
Se connecte au WebSocket JSON-RPC de Kodi et affiche les notifications reçues.
Usage: python3 listen_kodi_ws.py [HOST] [PORT] [USER] [PASS]
Ex: python3 listen_kodi_ws.py 127.0.0.1 8080
Si Kodi a auth HTTP activée, passe user/password.
"""
import sys
import json
import time
import base64
from websocket import WebSocketApp

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
USER = sys.argv[3] if len(sys.argv) > 3 else None
PASS = sys.argv[4] if len(sys.argv) > 4 else None

url = f"ws://{HOST}:{PORT}/jsonrpc"
headers = None
if USER and PASS:
    token = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
    headers = [f"Authorization: Basic {token}"]

def on_open(ws):
    print(f"[{time.strftime('%H:%M:%S')}] connected to {url}")
    # Optionally send a request to subscribe to notifications (ws server already sends them)
    # but we'll rely on notifications pushed by Kodi.

def on_message(ws, message):
    try:
        data = json.loads(message)
    except Exception:
        print("RAW:", message)
        return

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    # Pretty print the method and params of notifications
    if "method" in data:
        method = data.get("method")
        params = data.get("params", {})
        print(f"\n[{ts}] METHOD: {method}")
        # print light summary
        print(json.dumps(params, indent=2, ensure_ascii=False))
    else:
        print(f"\n[{ts}] RESPONSE: {json.dumps(data, indent=2, ensure_ascii=False)}")

def on_error(ws, err):
    print("ERROR:", err)

def on_close(ws, code, reason):
    print(f"[{time.strftime('%H:%M:%S')}] closed: {code} {reason}")

if __name__ == "__main__":
    ws = WebSocketApp(url,
                      header=headers,
                      on_open=on_open,
                      on_message=on_message,
                      on_error=on_error,
                      on_close=on_close)
    try:
        ws.run_forever()
    except KeyboardInterrupt:
        print("quit")