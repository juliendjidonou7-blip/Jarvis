import os
import time
import json
import threading
import websocket
from http.server import BaseHTTPRequestHandler, HTTPServer

TOKEN = os.getenv("DERIV_TOKEN")
APP_ID = 1089
PORT = int(os.getenv("PORT", 10000))

# Petit serveur pour Render - pour garder le Web Service en vie
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Jarvis en ligne")
    def log_message(self, *args):
        pass

def run_server():
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

threading.Thread(target=run_server, daemon=True).start()

print(f"Jarvis demarre... serveur sur port {PORT}")

if not TOKEN:
    print("ERREUR: DERIV_TOKEN manquant")
    while True:
        time.sleep(10)
else:
    print("TOKEN OK, connexion a Deriv...")

    def on_message(ws, message):
        data = json.loads(message)
        print("Recu:", data)
        if "authorize" in data:
            print("Connecte a Deriv OK")
            ws.send(json.dumps({"balance": 1}))
        if "balance" in data:
            print("Balance:", data["balance"])

    def on_error(ws, error):
        print("Erreur", error)

    def on_close(ws, code, msg):
        print("Connexion fermee, reconnexion dans 10s...")
        time.sleep(10)
        start()

    def on_open(ws):
        print("Websocket ouvert, envoi du token...")
        ws.send(json.dumps({"authorize": TOKEN}))

    def start():
        url = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
        ws = websocket.WebSocketApp(
            url,
            header={
                "Origin": "https://app.deriv.com",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        ws.run_forever()

    start()