import os
import time
import json
import threading
import asyncio
import websockets
from http.server import BaseHTTPRequestHandler, HTTPServer

TOKEN = os.getenv("DERIV_TOKEN")
APP_ID = 1089
PORT = int(os.getenv("PORT", 10000))

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

async def main():
    if not TOKEN:
        print("ERREUR: DERIV_TOKEN manquant")
        while True:
            await asyncio.sleep(10)
        return

    print("TOKEN OK, connexion a Deriv...")
    urls = [
        f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}",
        f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}",
    ]

    headers = {
        "Origin": "https://app.deriv.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for url in urls:
        print(f"Essai: {url}")
        try:
            async with websockets.connect(url, additional_headers=headers) as ws:
                print("Websocket ouvert, envoi du token...")
                await ws.send(json.dumps({"authorize": TOKEN}))
                async for message in ws:
                    data = json.loads(message)
                    print("Recu:", data)
                    if "authorize" in data:
                        print("Connecte a Deriv OK")
                        await ws.send(json.dumps({"balance": 1}))
                    if "balance" in data:
                        print("Balance:", data["balance"])
                return
        except Exception as e:
            print(f"Erreur sur {url}: {e}")

    print("Les 2 adresses ont echoue, reconnexion dans 10s...")
    await asyncio.sleep(10)
    await main()

if __name__ == "__main__":
    asyncio.run(main())