import json
import asyncio
import threading
import websockets

TOKEN = "pat_8266112edbea6a1f136fc85482899b2422f63537de0933fdbb8e19a7b7a5e9d7"
APP_ID = 1089

async def keep_alive(ws):
    while True:
        await asyncio.sleep(25)
        try:
            await ws.send(json.dumps({"ping": 1}))
        except Exception:
            break

async def bot():
    url = "wss://" + "ws." + "derivws.com" + "/websockets/v3?app_id=" + str(APP_ID)
    headers = {"Origin": "https://deriv.com", "User-Agent": "Mozilla/5.0"}
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

def start_bot():
    asyncio.run(bot())

threading.Thread(target=start_bot, daemon=True).start()

def application(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8")])
    return [b"Jarvis actif"]
