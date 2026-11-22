import os
import sys
import site
sys.path.append(site.getusersitepackages())

import json
import asyncio
import threading
from datetime import datetime, timezone
import websockets
from smc_engine import Config, Bars, SMCSignalEngine

TOKEN = os.environ.get("DERIV_TOKEN", "")
APP_ID = 1089
DEMO_ONLY = True

TF_SECONDS = {"M5": 300, "M15": 900, "H4": 14400, "W1": 604800}

ENGINES = {
    "frxXAUUSD": SMCSignalEngine(Config(symbol="frxXAUUSD", trading_mode="DAY")),
    "frxGBPUSD": SMCSignalEngine(Config(symbol="frxGBPUSD", trading_mode="SWING")),
    "cryBTCUSD": SMCSignalEngine(Config(symbol="cryBTCUSD", trading_mode="SWING")),
}

STATUS = {
    "connexion": "Initialisation...",
    "compte": "Inconnu",
    "solde": "0.00",
    "actifs": {
        "frxXAUUSD": "En attente du premier cycle...",
        "frxGBPUSD": "En attente du premier cycle...",
        "cryBTCUSD": "En attente du premier cycle...",
    },
    "derniers_ordres": [],
}

async def rpc(ws, payload: dict) -> dict:
    await ws.send(json.dumps(payload))
    while True:
        raw = await ws.recv()
        data = json.loads(raw)
        if data.get("msg_type") == "ping":
            continue
        return data

async def fetch_closed_bars(ws, symbol: str, tf: str, count: int) -> Bars:
    resp = await rpc(ws, {
        "ticks_history": symbol,
        "adjust_start_time": 1,
        "count": count + 1,
        "end": "latest",
        "style": "candles",
        "granularity": TF_SECONDS[tf],
    })
    if "error" in resp:
        raise RuntimeError(resp["error"]["message"])
    candles = resp.get("candles", [])[:-1]
    return Bars(
        open=[float(c["open"]) for c in candles],
        high=[float(c["high"]) for c in candles],
        low=[float(c["low"]) for c in candles],
        close=[float(c["close"]) for c in candles],
        time=[int(c["epoch"]) for c in candles],
    )

async def execute_multiplier_order(ws, signal: dict, balance: float):
    contract_type = "MULTUP" if signal["side"] == "BUY" else "MULTDOWN"
    stake = max(5.0, round(balance * 0.01, 2))
    resp = await rpc(ws, {
        "buy": 1,
        "price": stake,
        "parameters": {
            "amount": stake,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": "USD",
            "symbol": signal["symbol"],
            "multiplier": signal["multiplier"],
        },
    })
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if "error" in resp:
        log = f"[{ts}] ECHEC {signal['name']} {signal['side']} : {resp['error']['message']}"
    else:
        cid = resp["buy"]["contract_id"]
        log = f"[{ts}] ORDRE DEMO #{cid} | {signal['name']} {signal['side']} | Mise: {stake}$ | Entree: {signal['entry']}"
    STATUS["derniers_ordres"].insert(0, log)
    STATUS["derniers_ordres"] = STATUS["derniers_ordres"][:15]

async def bot():
    url = "wss://" + "frontend." + "derivws.com" + "/websockets/v3?app_id=" + str(APP_ID)
    headers = {"Origin": "https://app.deriv.com"}
    while True:
        try:
            async with websockets.connect(url, additional_headers=headers) as ws:
                auth = await rpc(ws, {"authorize": TOKEN})
                if "error" in auth:
                    STATUS["connexion"] = "Erreur Auth : " + auth["error"]["message"]
                    await asyncio.sleep(15)
                    continue

                info = auth["authorize"]
                is_virtual = bool(info.get("is_virtual", 0))
                balance = float(info.get("balance", 0.0))
                STATUS["connexion"] = "Connecte a Deriv OK"
                STATUS["compte"] = f"{info.get('loginid', '')} ({'DEMO VRTC' if is_virtual else 'REEL'})"
                STATUS["solde"] = f"{balance:.2f} {info.get('currency', 'USD')}"

                if DEMO_ONLY and not is_virtual:
                    STATUS["connexion"] = "BLOQUE : Utilisez un token DEMO VRTC"
                    await asyncio.sleep(30)
                    continue

                while True:
                    bal_resp = await rpc(ws, {"balance": 1})
                    if "balance" in bal_resp:
                        balance = float(bal_resp["balance"]["balance"])
                        STATUS["solde"] = f"{balance:.2f} {bal_resp['balance']['currency']}"

                    for sym, engine in ENGINES.items():
                        try:
                            htf, mtf, ltf = engine.cfg.timeframes()
                            bars_h = await fetch_closed_bars(ws, sym, htf, engine.cfg.tf_high_bars)
                            bars_m = await fetch_closed_bars(ws, sym, mtf, engine.cfg.tf_mid_bars)
                            bars_l = await fetch_closed_bars(ws, sym, ltf, engine.cfg.tf_low_bars)

                            trend = engine.update_trend_zone(bars_h, bars_m)
                            signal = engine.update_entry_bar(bars_l)

                            biais_txt = {1: "HAUSSIER", -1: "BAISSIER", 0: "NEUTRE"}[trend["trend_bias"]]
                            sess_txt = "Session OUVERTE" if trend["session_open"] else "Hors session"
                            now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

                            STATUS["actifs"][sym] = (
                                f"{trend['symbol']} [{trend['mode']} {trend['timeframes']}] | "
                                f"{sess_txt} | Biais: {biais_txt} | Etape: {trend['state']}/3 | "
                                f"Trades: {engine.trades_today}/{engine.cfg.max_trades_per_day} ({now_str})"
                            )
                            if signal is not None:
                                await execute_multiplier_order(ws, signal, balance)
                        except Exception as sym_err:
                            STATUS["actifs"][sym] = f"{sym} : Erreur ({sym_err})"

                    await asyncio.sleep(60)
        except Exception as e:
            STATUS["connexion"] = f"Reconnexion... ({e})"
            await asyncio.sleep(10)

def start_bot():
    asyncio.run(bot())

threading.Thread(target=start_bot, daemon=True).start()

def application(environ, start_response):
    lines = [
        "=== JARVIS SMC BOT (MODE DEMO VRTC) ===",
        f"Statut   : {STATUS['connexion']}",
        f"Compte   : {STATUS['compte']}",
        f"Solde    : {STATUS['solde']}",
        "",
        "--- ANALYSE DES MARCHES EN DIRECT ---",
        f"* {STATUS['actifs']['frxXAUUSD']}",
        f"* {STATUS['actifs']['frxGBPUSD']}",
        f"* {STATUS['actifs']['cryBTCUSD']}",
        "",
        "--- DERNIERS ORDRES EXECUTES ---",
    ]
    lines.extend(STATUS["derniers_ordres"] or ["Aucun signal valide pour le moment."])
    body = "\n".join(lines).encode("utf-8")
    start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8")])
    return [body]
