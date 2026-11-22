import os
import json
import asyncio
import websockets

TOKEN = "pat_4286a58e4d40696749af30008aa863ebffdcf75ca34aa48a4a8ae178bb225079"
APP_ID = 351A317fd2tFf6a3SLIGH35
async def keep_alive(ws):
    while True:
        await asyncio.sleep(25)
        try:
            await ws.send(json.dumps({"ping": 1}))
        except Exception:
            break

async def main():
    if not TOKEN:
        print("ERREUR: DERIV_TOKEN manquant")
        return

    url = f"wss://://derivws.com{APP_ID}"
    headers = {
        "Origin": "https://deriv.com",
        "User-Agent": "Mozilla/5.0"
    }

    while True:
        print("Connexion a Deriv...")
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
                        print("Balance actuelle:", data["balance"]["balance"], data["balance"]["currency"])

                ping_task.cancel()
        except Exception as e:
            print("Erreur de connexion:", e)

        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())

