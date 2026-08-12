"""
gui/app.py
Dashboard NiceGUI + Plotly: candlestick ao vivo, indicadores, sinais e curva de equity.
Roda em http://localhost:8080
"""
import pandas as pd
import plotly.graph_objects as go
import yaml
from nicegui import ui
from sqlalchemy import create_engine, text


def load_config(path="config/config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CFG = load_config()
d = CFG["database"]
ENGINE = create_engine(f"postgresql+psycopg2://{d['user']}:{d['password']}@{d['host']}:{d['port']}/{d['dbname']}")

SYMBOLS = CFG["symbols"]
TIMEFRAMES = CFG["timeframes"]
REFRESH = CFG["gui"].get("refresh_seconds", 2)
state = {"symbol": SYMBOLS[0], "timeframe": TIMEFRAMES[0]}


def fetch_candles(symbol, timeframe, limit=150):
    sql = text("SELECT time, open, high, low, close FROM candles WHERE symbol=:s AND timeframe=:tf ORDER BY time DESC LIMIT :l")
    with ENGINE.connect() as conn:
        df = pd.read_sql(sql, conn, params={"s": symbol, "tf": timeframe, "l": limit})
    return df.sort_values("time")


def fetch_latest_indicator(symbol, timeframe):
    sql = text("SELECT * FROM indicators WHERE symbol=:s AND timeframe=:tf ORDER BY time DESC LIMIT 1")
    with ENGINE.connect() as conn:
        df = pd.read_sql(sql, conn, params={"s": symbol, "tf": timeframe})
    return df.iloc[0] if not df.empty else None


def fetch_recent_signals(limit=15):
    sql = text("SELECT time, symbol, direction, score, blocked_reason FROM signals ORDER BY time DESC LIMIT :l")
    with ENGINE.connect() as conn:
        return pd.read_sql(sql, conn, params={"l": limit})


def fetch_equity_curve(limit=500):
    sql = text("SELECT time, balance, equity FROM equity_curve ORDER BY time DESC LIMIT :l")
    with ENGINE.connect() as conn:
        df = pd.read_sql(sql, conn, params={"l": limit})
    return df.sort_values("time")


def build_candlestick_fig(df, symbol):
    fig = go.Figure(data=[go.Candlestick(x=df["time"], open=df["open"], high=df["high"],
                                          low=df["low"], close=df["close"])])
    fig.update_layout(title=symbol, template="plotly_dark", height=420,
                       margin=dict(l=10, r=10, t=40, b=10), xaxis_rangeslider_visible=False)
    return fig


def build_equity_fig(df):
    fig = go.Figure()
    if not df.empty:
        fig.add_trace(go.Scatter(x=df["time"], y=df["equity"], mode="lines", name="Equity"))
        fig.add_trace(go.Scatter(x=df["time"], y=df["balance"], mode="lines", name="Balance", line=dict(dash="dot")))
    fig.update_layout(title="Curva de Equity", template="plotly_dark", height=280,
                       margin=dict(l=10, r=10, t=40, b=10))
    return fig


@ui.page("/")
def main_page():
    ui.dark_mode().enable()
    with ui.header().classes("items-center justify-between"):
        ui.label("CFD Adaptive System - Fase 1").classes("text-xl font-bold")
        ui.label("Conta DEMO - motor tecnico + correlacao + VaR de portfolio").classes("text-xs text-yellow-400")

    with ui.row().classes("w-full gap-4"):
        symbol_select = ui.select(SYMBOLS, value=state["symbol"], label="Simbolo").classes("w-64")
        tf_select = ui.select(TIMEFRAMES, value=state["timeframe"], label="Timeframe").classes("w-32")

        def on_change():
            state["symbol"] = symbol_select.value
            state["timeframe"] = tf_select.value

        symbol_select.on("update:model-value", lambda e: on_change())
        tf_select.on("update:model-value", lambda e: on_change())

    with ui.row().classes("w-full gap-4"):
        with ui.card().classes("w-2/3"):
            candle_plot = ui.plotly(build_candlestick_fig(pd.DataFrame(columns=["time","open","high","low","close"]), state["symbol"]))
        with ui.card().classes("w-1/3"):
            ui.label("Indicadores atuais").classes("font-bold")
            regime_label = ui.label("Regime: -")
            score_label = ui.label("Score: -")
            rsi_label = ui.label("RSI: -")
            atr_label = ui.label("ATR: -")

    with ui.row().classes("w-full gap-4"):
        with ui.card().classes("w-1/2"):
            equity_plot = ui.plotly(build_equity_fig(pd.DataFrame()))
        with ui.card().classes("w-1/2"):
            ui.label("Sinais recentes").classes("font-bold")
            signals_table = ui.table(
                columns=[{"name": "time", "label": "Hora", "field": "time"},
                         {"name": "symbol", "label": "Simbolo", "field": "symbol"},
                         {"name": "direction", "label": "Direcao", "field": "direction"},
                         {"name": "score", "label": "Score", "field": "score"},
                         {"name": "blocked_reason", "label": "Bloqueio", "field": "blocked_reason"}],
                rows=[], row_key="time").classes("w-full")

    def refresh():
        df = fetch_candles(state["symbol"], state["timeframe"])
        candle_plot.figure = build_candlestick_fig(df, state["symbol"])
        candle_plot.update()

        ind = fetch_latest_indicator(state["symbol"], state["timeframe"])
        if ind is not None:
            regime_label.text = f"Regime: {ind['regime']} (conf. {ind['regime_confidence']:.1f}%)"
            score_label.text = f"Score: {ind['signal_score']:.1f}/100"
            rsi_label.text = f"RSI: {ind['rsi']:.2f}" if pd.notna(ind["rsi"]) else "RSI: -"
            atr_label.text = f"ATR: {ind['atr']:.5f}" if pd.notna(ind["atr"]) else "ATR: -"

        eq = fetch_equity_curve()
        equity_plot.figure = build_equity_fig(eq)
        equity_plot.update()

        sig = fetch_recent_signals()
        signals_table.rows = sig.to_dict("records")

    ui.timer(REFRESH, refresh)
    refresh()


ui.run(host=CFG["gui"].get("host", "0.0.0.0"), port=CFG["gui"].get("port", 8080), title="CFD Adaptive System")
