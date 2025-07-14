CREATE TABLE IF NOT EXISTS stock_prices (
    timestamp TIMESTAMPTZ NOT NULL,
    stock_name VARCHAR(255) NOT NULL,
    exchange_name VARCHAR(255) NOT NULL,
    price NUMERIC NOT NULL
);

-- Index to improve time-based queries for individual stocks
CREATE INDEX IF NOT EXISTS idx_stock_prices_ts_name ON stock_prices (stock_name, timestamp DESC);
