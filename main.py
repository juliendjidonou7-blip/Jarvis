import os
import json
import threading
import asyncio
import websockets
from http.server import BaseHTTPRequestHandler, HTTPServer

TOKEN = os.getenv("DERIV_TOKEN")
APP_ID = 1089
PORT = int(os.getenv("PORT", 7860))  # 7860 par défaut (compatible Hugging Face et Render/Koyeb)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Jarvis en ligne")
    def log_message(self, *args):
        pass

def run_server():
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

async def keep_alive(ws):
    while True:
        await asyncio.sleep(25)
        try:
            await ws.send(json.dumps({"ping": 1}))
        except Exception:
            break

async def main():
    if not TOKEN:
        print("ERREUR: DERIV_TOKEN manquant dans les variables d'environnement")
        while True:
            await asyncio.sleep(30)

    print("TOKEN OK, demarrage de Jarvis...")
    url = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
    headers = {
        "Origin": "https://app.deriv.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    while True:
        print(f"Connexion a {url}...")
        try:
            async with websockets.connect(url, additional_headers=headers) as ws:
                print("Websocket ouvert, envoi du token...")
                await ws.send(json.dumps({"authorize": TOKEN}))
                ping_task = asyncio.create_task(keep_alive(ws))

                async for message in ws:
                    data = json.loads(message)
                    if "error" in data:
                        print("Erreur Deriv:", data["error"]["message"])
                        break
                    if "authorize" in data:
                        print("Connecte a Deriv OK !")
                        await ws.send(json.dumps({"balance": 1, "subscribe": 1}))
                    elif "balance" in data:
                        print("Balance:", data["balance"]["balance"], data["balance"]["currency"])
                    elif "pong" not in data:
                        print("Recu:", data)

                ping_task.cancel()
        except Exception as e:
            print(f"Erreur de connexion: {e}")

        print("Reconnexion dans 10 secondes...")
        await asyncio.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    print(f"Serveur HTTP actif sur le port {PORT}")
    asyncio.run(main())
