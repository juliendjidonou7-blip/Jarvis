from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence, Optional, Dict, Tuple

SYMBOL_SPECS: Dict[str, dict] = {
    "frxXAUUSD": {
        "name": "XAUUSD",
        "allowed_modes": ("DAY",),
        "default_mode": "DAY",
        "DAY":   {"min_zone_mid": 3.0,    "min_zone_low": 1.0,    "sl_buffer": 0.50},
        "use_sessions": True,
        "decimals": 2,
        "multiplier": 100,
    },
    "frxGBPUSD": {
        "name": "GBPUSD",
        "allowed_modes": ("SWING", "DAY"),
        "default_mode": "SWING",
        "SWING": {"min_zone_mid": 0.0025, "min_zone_low": 0.0008, "sl_buffer": 0.0005},
        "DAY":   {"min_zone_mid": 0.0012, "min_zone_low": 0.0004, "sl_buffer": 0.0003},
        "use_sessions": True,
        "decimals": 5,
        "multiplier": 100,
    },
    "cryBTCUSD": {
        "name": "BTCUSD",
        "allowed_modes": ("SWING", "DAY"),
        "default_mode": "SWING",
        "SWING": {"min_zone_mid": 350.0,  "min_zone_low": 100.0,  "sl_buffer": 60.0},
        "DAY":   {"min_zone_mid": 150.0,  "min_zone_low": 50.0,   "sl_buffer": 30.0},
        "use_sessions": False,
        "decimals": 2,
        "multiplier": 10,
    },
}

ALLOWED_SYMBOLS = tuple(SYMBOL_SPECS.keys())


@dataclass(frozen=True)
class Config:
    symbol: str = "frxXAUUSD"
    trading_mode: Optional[str] = None
    swing_lookback: int = 2
    tf_high_bars: int = 60
    tf_mid_bars: int = 200
    tf_low_bars: int = 200
    setup_timeout_mid_bars: int = 15
    sweep_lookback_bars: int = 20
    entry_timeout_low_bars: int = 10
    use_liquidity_tp: bool = True
    risk_reward_ratio: float = 3.0
    risk_percent: float = 1.0
    max_daily_loss: float = 50.0
    max_trades_per_day: int = 2
    max_losses_per_day: int = 3
    session1_start_utc: int = 9
    session1_end_utc: int = 11
    session2_start_utc: int = 15
    session2_end_utc: int = 17

    def __post_init__(self):
        if self.symbol not in SYMBOL_SPECS:
            raise ValueError(f"Symbole non autorisé : {self.symbol}")
        spec = SYMBOL_SPECS[self.symbol]
        mode = (self.trading_mode or spec["default_mode"]).upper()
        if mode not in spec["allowed_modes"]:
            raise ValueError(f"Mode '{mode}' interdit pour {spec['name']}.")
        object.__setattr__(self, "trading_mode", mode)

    def timeframes(self) -> Tuple[str, str, str]:
        return ("W1", "H4", "M15") if self.trading_mode == "SWING" else ("H4", "M15", "M5")

    @property
    def spec(self) -> dict:
        return SYMBOL_SPECS[self.symbol]

    @property
    def thresholds(self) -> dict:
        return self.spec[self.trading_mode]


@dataclass
class Bars:
    open: Sequence[float]
    high: Sequence[float]
    low: Sequence[float]
    close: Sequence[float]
    time: Sequence[object] = ()

    def __post_init__(self):
        n = len(self.close)
        if not all(len(x) == n for x in (self.open, self.high, self.low)):
            raise ValueError("OHLC: longueurs différentes")
        if self.time and len(self.time) != n:
            raise ValueError("Le tableau time doit avoir la même longueur que OHLC")


@dataclass
class Zone:
    valid: bool = False
    low: float = 0.0
    high: float = 0.0
    kind: str = ""
    index: int = -1


@dataclass
class Setup:
    state: int = 0
    direction: int = 0
    mid_zone: Zone = field(default_factory=Zone)
    zone_touched: bool = False
    mid_bars_elapsed: int = 0
    wait_counter: int = 0
    sweep_level: float = 0.0
    sweep_time: object = None
    low_zone: Zone = field(default_factory=Zone)

    def reset(self):
        self.state = 0
        self.direction = 0
        self.mid_zone = Zone()
        self.zone_touched = False
        self.mid_bars_elapsed = 0
        self.wait_counter = 0
        self.sweep_level = 0.0
        self.sweep_time = None
        self.low_zone = Zone()


def is_in_trading_session(symbol: str, cfg: Config, utc_now: Optional[datetime] = None) -> bool:
    if not SYMBOL_SPECS[symbol]["use_sessions"]:
        return True
    now = utc_now or datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return False
    h = now.hour
    return (cfg.session1_start_utc <= h < cfg.session1_end_utc) or (
        cfg.session2_start_utc <= h < cfg.session2_end_utc
    )


def find_swings(b: Bars, lookback: int):
    highs, lows = [], []
    for i in range(lookback, len(b.close) - lookback):
        if all(b.high[i] >= b.high[i - j] and b.high[i] >= b.high[i + j] for j in range(1, lookback + 1)):
            highs.append((i, float(b.high[i])))
        if all(b.low[i] <= b.low[i - j] and b.low[i] <= b.low[i + j] for j in range(1, lookback + 1)):
            lows.append((i, float(b.low[i])))
    return highs, lows


def detect_last_bos(closes, swing_highs, swing_lows):
    last = len(closes) - 1
    if last < 0:
        return 0, -1
    direction, break_idx = 0, -1
    if swing_highs:
        i, p = swing_highs[-1]
        if i < last and closes[-1] > p:
            direction, break_idx = 1, i
    if swing_lows:
        i, p = swing_lows[-1]
        if i < last and closes[-1] < p and (direction == 0 or i > break_idx):
            direction, break_idx = -1, i
    return direction, break_idx


def structure_bias(b: Bars, lookback: int) -> int:
    sh, sl = find_swings(b, lookback)
    if len(sh) < 2 or len(sl) < 2:
        return 0
    hh = sh[-1][1] > sh[-2][1]
    lh = sh[-1][1] < sh[-2][1]
    hl = sl[-1][1] > sl[-2][1]
    ll = sl[-1][1] < sl[-2][1]
    if hh and hl:
        return 1
    if lh and ll:
        return -1
    return 0


def find_fvg(b: Bars, direction: int, min_size: float, search_from: int = 0) -> Zone:
    n = len(b.close)
    for i in range(n - 1, max(2, search_from + 2) - 1, -1):
        if direction == 1 and b.high[i - 2] < b.low[i]:
            lo, hi = float(b.high[i - 2]), float(b.low[i])
            mitigated = any(b.close[k] < lo for k in range(i + 1, n))
            if hi - lo >= min_size and not mitigated:
                return Zone(True, lo, hi, "FVG", i)
        elif direction == -1 and b.low[i - 2] > b.high[i]:
            lo, hi = float(b.high[i]), float(b.low[i - 2])
            mitigated = any(b.close[k] > hi for k in range(i + 1, n))
            if hi - lo >= min_size and not mitigated:
                return Zone(True, lo, hi, "FVG", i)
    return Zone(kind="FVG")


def find_ob(b: Bars, direction: int, lookback: int, search_from: int = 0) -> Zone:
    sub = Bars(b.open[search_from:], b.high[search_from:], b.low[search_from:], b.close[search_from:])
    if len(sub.close) < lookback * 2 + 5:
        return Zone(kind="OB")
    sh, sl = find_swings(sub, lookback)
    bos, break_idx = detect_last_bos(sub.close, sh, sl)
    if bos != direction or break_idx < 0:
        return Zone(kind="OB")
    ob = None
    for i in range(break_idx, -1, -1):
        opposite = (sub.close[i] < sub.open[i]) if direction == 1 else (sub.close[i] > sub.open[i])
        if opposite:
            ob = (float(sub.low[i]), float(sub.high[i]))
            break
    if ob is None:
        return Zone(kind="OB")
    lo, hi = ob
    for k in range(break_idx + 1, len(sub.close)):
        if (direction == 1 and sub.close[k] < lo) or (direction == -1 and sub.close[k] > hi):
            return Zone(kind="OB")
    return Zone(True, lo, hi, "OB", search_from + break_idx)


def find_zone(b: Bars, direction: int, min_fvg: float, lookback: int, search_from: int = 0) -> Zone:
    z = find_fvg(b, direction, min_fvg, search_from)
    return z if z.valid else find_ob(b, direction, lookback, search_from)


def detect_choch(b: Bars, lookback: int, search_from: int) -> int:
    sub = Bars(b.open[search_from:], b.high[search_from:], b.low[search_from:], b.close[search_from:])
    if len(sub.close) < lookback * 2 + 3:
        return 0
    sh, sl = find_swings(sub, lookback)
    return detect_last_bos(sub.close, sh, sl)


def check_liquidity_sweep(b: Bars, direction: int, lookback_bars: int, swing_lookback: int):
    sh, sl = find_swings(b, swing_lookback)
    n = len(b.close)
    refs = sl if direction == 1 else sh
    if not refs:
        return None
    ref_i, ref_price = refs[-1]
    for k in range(ref_i + 1, n):
        swept = (b.low[k] < ref_price and b.close[k] > ref_price) if direction == 1 else (
            b.high[k] > ref_price and b.close[k] < ref_price
        )
        if swept and n - 1 - k <= lookback_bars:
            return {"level": float(b.low[k] if direction == 1 else b.high[k]), "index": k}
    return None


def liquidity_target(b: Bars, direction: int, entry: float, lookback: int) -> Optional[float]:
    sh, sl = find_swings(b, lookback)
    candidates = [p for _, p in (sh if direction == 1 else sl) if (p > entry if direction == 1 else p < entry)]
    if not candidates:
        return None
    return min(candidates) if direction == 1 else max(candidates)


class SMCSignalEngine:
    def __init__(self, config: Config = Config()):
        self.cfg = config
        self.setup = Setup()
        self.trades_today = 0
        self.losses_today = 0
        self.daily_pnl = 0.0
        self.current_day = datetime.now(timezone.utc).date()
        self.last_mid_time = None
        self.last_low_time = None

    def _refresh_day(self):
        today = datetime.now(timezone.utc).date()
        if today != self.current_day:
            self.current_day = today
            self.trades_today = 0
            self.losses_today = 0
            self.daily_pnl = 0.0

    def can_trade(self) -> bool:
        self._refresh_day()
        c = self.cfg
        if self.trades_today >= c.max_trades_per_day:
            return False
        if self.losses_today >= c.max_losses_per_day:
            return False
        if self.daily_pnl <= -abs(c.max_daily_loss):
            return False
        return is_in_trading_session(c.symbol, c)

    def update_trend_zone(self, high_tf_bars: Bars, mid_tf_bars: Bars):
        c = self.cfg
