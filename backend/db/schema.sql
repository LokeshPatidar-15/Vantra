-- Vantra Database Schema
-- Day 3: users table
-- Day 10: candles table (OHLCV market data)
-- Safe to run more than once.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS candles (
    symbol     VARCHAR(20)      NOT NULL,   -- our name, e.g. 'XAUUSD'
    timeframe  VARCHAR(5)       NOT NULL,   -- '1m','5m','15m','30m','1h','4h','1d'
    open_time  TIMESTAMPTZ      NOT NULL,   -- candle OPEN time, UTC
    open       DOUBLE PRECISION NOT NULL,
    high       DOUBLE PRECISION NOT NULL,
    low        DOUBLE PRECISION NOT NULL,
    close      DOUBLE PRECISION NOT NULL,
    volume     DOUBLE PRECISION,            -- NULL when the provider has no volume
    source     VARCHAR(20)      NOT NULL,   -- 'binance' or 'twelvedata'
    PRIMARY KEY (symbol, timeframe, open_time),
    CHECK (open > 0 AND high > 0 AND low > 0 AND close > 0),
    CHECK (high >= GREATEST(open, close)),
    CHECK (low <= LEAST(open, close))
);
