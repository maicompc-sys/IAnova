"""
engine/indicator_engine.py

Motor tecnico classico. Indicadores (EMA, RSI, ATR, Bollinger) implementados
nativamente com pandas/numpy (sem pandas_ta) para reduzir dependencia externa em
producao e permitir testes unitarios sem libs pesadas. Funcoes de calculo sao puras.
Imports de sqlalchemy/river sao "lazy" (dentro das funcoes de I/O).
"""
import logging
import time

import numpy as np
import pandas as pd
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [engine] %(message)s")
log = logging.getLogger(__name__)


def load_config(path="config/config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def db_engine(cfg):
    from sqlalchemy import create_engine
    d = cfg["database"]
    url = f"postgresql+psycopg2://{d['user']}:{d['password']}@{d['host']}:{d['port']}/{d['dbname']}"
    return create_engine(url)


class RegimeDetector:
    def __init__(self, delta=0.002):
        from river import drift
        self._drift_module = drift
        self.detectors = {}
        self.delta = delta

    def _get(self, key):
        if key not in self.detectors:
            self.detectors[key] = self._drift_module.ADWIN(delta=self.delta)
        return self.detectors[key]

    def update(self, key, value):
        det = self._get(key)
        det.update(value)
        return det.drift_detected


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def _rsi(close: pd.Series, length: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False).mean()


def _bollinger(close: pd.Series, length: int, std_mult: float):
    mid = close.rolling(length).mean()
    std = close.rolling(length).std()
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    return upper, lower


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """Average Directional Index (ADX) — mede a FORCA da tendencia (0-100).
    Valores > 25 indicam tendencia forte. Implementacao Wilder classica."""
    prev_high  = high.shift(1)
    prev_low   = low.shift(1)
    prev_close = close.shift(1)

    plus_dm  = np.where((high - prev_high) > (prev_low - low), np.maximum(high - prev_high, 0), 0)
    minus_dm = np.where((prev_low - low) > (high - prev_high), np.maximum(prev_low - low, 0), 0)

    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)

    tr_s   = pd.Series(tr).ewm(alpha=1 / length, adjust=False).mean()
    pdm_s  = pd.Series(plus_dm,  index=high.index).ewm(alpha=1 / length, adjust=False).mean()
    ndm_s  = pd.Series(minus_dm, index=high.index).ewm(alpha=1 / length, adjust=False).mean()

    pdi = 100 * pdm_s / tr_s.replace(0, np.nan)
    ndi = 100 * ndm_s / tr_s.replace(0, np.nan)
    dx  = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    return dx.ewm(alpha=1 / length, adjust=False).mean().fillna(0.0)


def _candle_pattern(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Detecta padroes de vela de confirmacao de tendencia.
    Retorna:  1 = bullish (engolfo altista ou martelo)
             -1 = bearish (engolfo baixista ou shooting star)
              0 = neutro"""
    body      = close - open_
    prev_body = body.shift(1)
    prev_open = open_.shift(1)
    prev_close= close.shift(1)
    candle_range = high - low
    upper_wick   = high - close.combine(open_, max)
    lower_wick   = close.combine(open_, min) - low

    # Engolfo altista: vela atual bullish envolve corpo anterior bearish
    bull_engulf = (body > 0) & (prev_body < 0) & (close > prev_open) & (open_ < prev_close)
    # Engolfo baixista
    bear_engulf = (body < 0) & (prev_body > 0) & (close < prev_open) & (open_ > prev_close)
    # Martelo (pavio inferior >= 2x corpo, pavio superior pequeno)
    hammer = (body > 0) & (lower_wick >= 2 * body.abs()) & (upper_wick <= 0.3 * body.abs())
    # Shooting star
    shooting = (body < 0) & (upper_wick >= 2 * body.abs()) & (lower_wick <= 0.3 * body.abs())

    pattern = pd.Series(0, index=close.index)
    pattern[bull_engulf | hammer]    =  1
    pattern[bear_engulf | shooting]  = -1
    return pattern


def compute_indicators(df: pd.DataFrame, cfg_engine: dict) -> pd.DataFrame:
    df = df.copy()
    df["ema_fast"]  = _ema(df["close"], cfg_engine["ema_fast"])
    df["ema_slow"]  = _ema(df["close"], cfg_engine["ema_slow"])
    df["rsi"]       = _rsi(df["close"], cfg_engine["rsi_period"])
    df["atr"]       = _atr(df["high"], df["low"], df["close"], cfg_engine["atr_period"])
    df["bb_upper"], df["bb_lower"] = _bollinger(
        df["close"], cfg_engine["bb_period"], cfg_engine["bb_std"]
    )
    df["adx"]           = _adx(df["high"], df["low"], df["close"], cfg_engine.get("adx_period", 14))
    df["candle_pattern"] = _candle_pattern(df["open"], df["high"], df["low"], df["close"])
    df["returns"]        = df["close"].pct_change()
    return df


def classify_regime(row: pd.Series, drift_flag: bool) -> tuple:
    if pd.isna(row["ema_fast"]) or pd.isna(row["ema_slow"]):
        return "range", 50.0
    ema_diff_pct = (row["ema_fast"] - row["ema_slow"]) / row["ema_slow"] * 100
    if ema_diff_pct > 0.10:
        regime = "trend_up"
    elif ema_diff_pct < -0.10:
        regime = "trend_down"
    else:
        regime = "range"
    confidence = min(100.0, abs(ema_diff_pct) * 400)
    if drift_flag:
        confidence = max(0.0, confidence - 20)
    return regime, round(confidence, 2)


def signal_score(row: pd.Series, regime: str, regime_confidence: float) -> float:
    """Calcula score de sinal (0-100) combinando regime, RSI, Bollinger,
    ADX (forca de tendencia) e padrao de vela (confirmacao de entrada).

    ADX >= 25 e obrigatorio para sinais de tendencia — bloqueia entradas em
    mercados laterais que eram a causa do win rate baixo nos backtests.
    Padrao de vela alinhado adiciona 15 pts extras de confianca.
    """
    score = 0.0

    # --- Bloco 1: regime + EMA confidence (max 40 pts) ---
    if regime in ("trend_up", "trend_down"):
        score += 0.4 * regime_confidence

    # --- Bloco 2: ADX — filtro de forca de tendencia (gate obrigatorio) ---
    adx = row.get("adx", 0.0)
    if pd.isna(adx):
        adx = 0.0
    adx_ok = (adx >= 25.0) if regime in ("trend_up", "trend_down") else True
    if not adx_ok:
        # Tendencia fraca: penaliza fortemente o score para bloquear o sinal
        return round(max(0.0, score - 30.0), 2)

    # --- Bloco 3: RSI (max 20 pts) ---
    if pd.notna(row["rsi"]):
        if regime == "trend_up" and row["rsi"] < 70:
            score += 20
        elif regime == "trend_down" and row["rsi"] > 30:
            score += 20
        elif regime == "range" and 40 <= row["rsi"] <= 60:
            score += 10

    # --- Bloco 4: Bollinger position (max 20 pts) ---
    if pd.notna(row.get("bb_upper")) and pd.notna(row.get("bb_lower")):
        band_width = row["bb_upper"] - row["bb_lower"]
        if band_width > 0:
            pos = (row["close"] - row["bb_lower"]) / band_width
            if regime == "trend_up" and pos < 0.8:
                score += 20
            elif regime == "trend_down" and pos > 0.2:
                score += 20
            elif regime == "range" and 0.3 <= pos <= 0.7:
                score += 15

    # --- Bloco 5: confirmacao de vela (bonus +15 pts) ---
    cp = row.get("candle_pattern", 0)
    if pd.notna(cp):
        if regime == "trend_up" and cp == 1:
            score += 15
        elif regime == "trend_down" and cp == -1:
            score += 15

    return round(min(100.0, score), 2)


def _safe(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return float(v)


def fetch_candles(engine, symbol, timeframe, limit=300):
    from sqlalchemy import text
    sql = text("""
        SELECT time, open, high, low, close FROM candles
        WHERE symbol = :symbol AND timeframe = :timeframe
        ORDER BY time DESC LIMIT :limit
    """)
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params={"symbol": symbol, "timeframe": timeframe, "limit": limit})
    return df.sort_values("time").reset_index(drop=True)


def persist_indicators(engine, symbol, timeframe, row, regime, regime_confidence, score):
    from sqlalchemy import text
    sql = text("""
        INSERT INTO indicators (time, symbol, timeframe, ema_fast, ema_slow, rsi, atr,
                                 bb_upper, bb_lower, regime, regime_confidence, signal_score)
        VALUES (:time, :symbol, :timeframe, :ema_fast, :ema_slow, :rsi, :atr,
                :bb_upper, :bb_lower, :regime, :regime_confidence, :signal_score)
        ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
            ema_fast = EXCLUDED.ema_fast, ema_slow = EXCLUDED.ema_slow,
            rsi = EXCLUDED.rsi, atr = EXCLUDED.atr,
            bb_upper = EXCLUDED.bb_upper, bb_lower = EXCLUDED.bb_lower,
            regime = EXCLUDED.regime, regime_confidence = EXCLUDED.regime_confidence,
            signal_score = EXCLUDED.signal_score;
    """)
    with engine.begin() as conn:
        conn.execute(sql, {
            "time": row["time"], "symbol": symbol, "timeframe": timeframe,
            "ema_fast": _safe(row["ema_fast"]), "ema_slow": _safe(row["ema_slow"]),
            "rsi": _safe(row["rsi"]), "atr": _safe(row["atr"]),
            "bb_upper": _safe(row.get("bb_upper")), "bb_lower": _safe(row.get("bb_lower")),
            "regime": regime, "regime_confidence": float(regime_confidence), "signal_score": float(score),
        })


def persist_signal(engine, symbol, direction, score, row):
    from sqlalchemy import text
    sql = text("INSERT INTO signals (time, symbol, direction, score) VALUES (:time, :symbol, :direction, :score)")
    with engine.begin() as conn:
        conn.execute(sql, {"time": row["time"], "symbol": symbol, "direction": direction, "score": score})


def run_once(cfg, engine, detector):
    for symbol in cfg["symbols"]:
        for timeframe in cfg["timeframes"]:
            df = fetch_candles(engine, symbol, timeframe)
            if len(df) < max(cfg["engine"]["bb_period"], cfg["engine"]["ema_slow"]) + 5:
                continue
            df = compute_indicators(df, cfg["engine"])
            last = df.iloc[-1]
            drift_flag = False
            if pd.notna(last["returns"]):
                drift_flag = detector.update(f"{symbol}:{timeframe}", float(last["returns"]))
            regime, regime_conf = classify_regime(last, drift_flag)
            score = signal_score(last, regime, regime_conf)
            persist_indicators(engine, symbol, timeframe, last, regime, regime_conf, score)
            min_score_cfg = cfg["engine"]["min_signal_score"]
            min_score = min_score_cfg.get(timeframe, 50) if isinstance(min_score_cfg, dict) else min_score_cfg
            if score >= min_score and regime != "range":
                direction = "BUY" if regime == "trend_up" else "SELL"
                persist_signal(engine, symbol, direction, score, last)
                log.info(f"[SINAL] {symbol} {timeframe} {direction} score={score} regime={regime}")


def main():
    cfg = load_config()
    engine = db_engine(cfg)
    detector = RegimeDetector(delta=cfg["engine"]["adwin_delta"])
    log.info("Motor de indicadores iniciado.")
    while True:
        try:
            run_once(cfg, engine, detector)
        except Exception as e:
            log.exception(f"Erro no ciclo de analise: {e}")
        time.sleep(5)


if __name__ == "__main__":
    main()
