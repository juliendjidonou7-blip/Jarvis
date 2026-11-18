import os
import time
import json
import websocket

TOKEN = os.getenv("DERIV_TOKEN")
APP_ID = 1089

print("Jarvis demarre...")

if not TOKEN:
    print("ERREUR: DERIV_TOKEN manquant sur Render")
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
        print("Erreur:", error)

    def on_close(ws, code, msg):
        print("Connexion fermee, reconnexion dans 5s...")
        time.sleep(5)
        start()

    def on_open(ws):
        print("Websocket ouvert, envoi du token...")
        ws.send(json.dumps({"authorize": TOKEN}))

    def start():
        url = f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}"
        ws = websocket.WebSocketApp(url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close)
        ws.run_forever()

    start()