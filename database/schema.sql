CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS candles (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    timeframe   TEXT NOT NULL,
    open        DOUBLE PRECISION NOT NULL,
    high        DOUBLE PRECISION NOT NULL,
    low         DOUBLE PRECISION NOT NULL,
    close       DOUBLE PRECISION NOT NULL,
    tick_volume BIGINT,
    spread      DOUBLE PRECISION,
    PRIMARY KEY (time, symbol, timeframe)
);
SELECT create_hypertable('candles', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_candles_symbol_tf ON candles (symbol, timeframe, time DESC);

CREATE TABLE IF NOT EXISTS indicators (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    timeframe   TEXT NOT NULL,
    ema_fast    DOUBLE PRECISION,
    ema_slow    DOUBLE PRECISION,
    rsi         DOUBLE PRECISION,
    atr         DOUBLE PRECISION,
    bb_upper    DOUBLE PRECISION,
    bb_lower    DOUBLE PRECISION,
    regime      TEXT,
    regime_confidence DOUBLE PRECISION,
    signal_score DOUBLE PRECISION,
    PRIMARY KEY (time, symbol, timeframe)
);
SELECT create_hypertable('indicators', 'time', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS correlations (
    time        TIMESTAMPTZ NOT NULL,
    symbol_a    TEXT NOT NULL,
    symbol_b    TEXT NOT NULL,
    timeframe   TEXT NOT NULL,
    correlation DOUBLE PRECISION,
    PRIMARY KEY (time, symbol_a, symbol_b, timeframe)
);
SELECT create_hypertable('correlations', 'time', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS portfolio_var (
    time            TIMESTAMPTZ NOT NULL,
    var_pct         DOUBLE PRECISION,
    var_amount      DOUBLE PRECISION,
    method          TEXT,
    confidence      DOUBLE PRECISION,
    horizon_days    INTEGER,
    exposures_json  TEXT,
    PRIMARY KEY (time, method)
);
SELECT create_hypertable('portfolio_var', 'time', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS signals (
    id          BIGSERIAL PRIMARY KEY,
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    direction   TEXT NOT NULL,
    score       DOUBLE PRECISION,
    position_size DOUBLE PRECISION,
    stop_loss   DOUBLE PRECISION,
    take_profit DOUBLE PRECISION,
    kelly_fraction DOUBLE PRECISION,
    blocked_reason TEXT,
    executed    BOOLEAN DEFAULT FALSE,
    mt5_ticket  BIGINT,
    result_pips DOUBLE PRECISION,
    closed_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_time ON signals (symbol, time DESC);

CREATE TABLE IF NOT EXISTS equity_curve (
    time        TIMESTAMPTZ NOT NULL,
    balance     DOUBLE PRECISION,
    equity      DOUBLE PRECISION,
    drawdown_pct DOUBLE PRECISION,
    PRIMARY KEY (time)
);
SELECT create_hypertable('equity_curve', 'time', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS anomaly_log (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    metric      TEXT NOT NULL,
    value       DOUBLE PRECISION,
    threshold   DOUBLE PRECISION,
    triggered   BOOLEAN,
    PRIMARY KEY (time, symbol, metric)
);
SELECT create_hypertable('anomaly_log', 'time', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS economic_events (
    id          BIGSERIAL PRIMARY KEY,
    event_time  TIMESTAMPTZ NOT NULL,
    currency    TEXT NOT NULL,
    impact      TEXT NOT NULL,
    title       TEXT,
    forecast    TEXT,
    previous    TEXT,
    actual      TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_time ON economic_events (event_time);
