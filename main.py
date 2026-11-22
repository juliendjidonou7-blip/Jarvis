import os
import json
import asyncio
import threading
import websockets
from http.server import BaseHTTPRequestHandler, HTTPServer

TOKEN = "pat_8266112edbea6a1f136fc85482899b2422f63537de0933fdbb8e19a7b7a5e9d7"
APP_ID = 1089

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Jarvis actif")
    def log_message(self, *args):
        pass

def run_web():
    port = int(os.environ.get("PORT", 8100))
    HTTPServer(("::", port), Handler).serve_forever()

async def keep_alive(ws):
    while True:
        await asyncio.sleep(25)
        try:
            await ws.send(json.dumps({"ping": 1}))
        except Exception:
            break

async def bot():
    url = "wss://" + "ws." + "://derivws.com" + str(APP_ID)
    headers = {"Origin": "https://app.deriv.com", "User-Agent": "Mozilla/5.0"}
    while True:
        try:
            async with websockets.connect(url, additional_headers=headers) as ws:
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
                ping_task.cancel()
        except Exception as e:
            print("Erreur:", e)
        await asyncio.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.run(bot())

