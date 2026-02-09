# Volatility Indicators API - Data Pipeline Setup Guide

## Overview

This guide walks builders through building a complete data ingestion pipeline that pulls OHLCV data from Injective and stores it efficiently for volatility metric calculations.

---

## System Architecture

```
┌─────────────────┐
│  Injective API  │  (REST + WebSocket)
└────────┬────────┘
         │
         ▼
┌──────────────────────┐
│  Data Ingestion      │  (Python/Node.js service)
│  - Fetch OHLCV       │  Polls every 1-5 minutes
│  - Store candles     │
│  - Handle errors     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  PostgreSQL DB       │  (Time-series data)
│  - candles table     │
│  - computed metrics  │
│  - indices for speed │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Computation Engine  │  (Runs every 1-5 min)
│  - Calc volatility   │
│  - Bollinger Bands   │
│  - ATR, Momentum     │
│  - Cache results     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Redis Cache         │  (Fast queries)
│  - Precomputed       │
│  - 1-5 min TTL       │
│  - Reduces DB load   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Your API Server     │  (FastAPI/Express)
│  - Query endpoints   │
│  - Rate limiting     │
│  - Documentation     │
└──────────────────────┘
```

---

## Step 1: Understand Injective's Data Sources

### A. Injective REST API Endpoints

Injective provides a public API for market data:

**Base URL:** `https://mainnet-api.injective.network` (for mainnet)

**Key endpoints:**
- `GET /api/exchange/v1/markets` — List all markets
- `GET /api/exchange/v1/markets/{market_id}` — Market details
- `GET /api/exchange/v1/orderbook/{market_id}` — Current orderbook
- `GET /api/exchange/v1/trades/{market_id}` — Recent trades
- `GET /api/exchange/v1/historical_candles` — Historical OHLCV data

### B. Injective SDK

For more reliable data access, use the official SDK:

**Python SDK:** `pip install injective-py`

```python
# Example from Injective SDK
from pyinjective.client import Client
from pyinjective import Address
import asyncio

async def get_candles():
    client = Client(network="mainnet")
    
    # Get historical candles for a market
    candles = await client.get_historical_candles(
        market_id="0x...",  # INJ/USDT market ID
        resolution=3600,     # 1 hour candles
        start_time=1704067200,
        end_time=1704153600
    )
    
    return candles
```

### C. What's Available

- **Timeframes:** 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M
- **History depth:** Varies by market (typically 1-5 years)
- **Data latency:** Near real-time (few seconds to minutes)
- **Rate limits:** Check with Injective, typically generous for public data

---

## Step 2: Database Schema

Set up PostgreSQL to store candles efficiently:

```sql
-- Main candles table
CREATE TABLE candles (
    id BIGSERIAL PRIMARY KEY,
    market_id VARCHAR(255) NOT NULL,
    resolution INT NOT NULL,           -- 60=1min, 3600=1hour, etc.
    timestamp BIGINT NOT NULL,         -- Unix timestamp (seconds)
    open NUMERIC(20, 8) NOT NULL,
    high NUMERIC(20, 8) NOT NULL,
    low NUMERIC(20, 8) NOT NULL,
    close NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(20, 8) NOT NULL,
    
    UNIQUE(market_id, resolution, timestamp),
    INDEX idx_market_time (market_id, timestamp DESC)
);

-- Precomputed volatility metrics
CREATE TABLE volatility_metrics (
    id BIGSERIAL PRIMARY KEY,
    market_id VARCHAR(255) NOT NULL,
    timestamp BIGINT NOT NULL,
    volatility_1h NUMERIC(10, 6),
    volatility_4h NUMERIC(10, 6),
    volatility_24h NUMERIC(10, 6),
    bb_upper NUMERIC(20, 8),
    bb_middle NUMERIC(20, 8),
    bb_lower NUMERIC(20, 8),
    atr NUMERIC(20, 8),
    momentum NUMERIC(10, 6),
    
    UNIQUE(market_id, timestamp),
    INDEX idx_market_time (market_id, timestamp DESC)
);

-- Track data ingestion status
CREATE TABLE ingest_status (
    market_id VARCHAR(255) PRIMARY KEY,
    last_candle_timestamp BIGINT,
    last_ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_count INT DEFAULT 0,
    last_error TEXT
);
```

### Why This Design:
- **UNIQUE constraints:** Prevent duplicates when reprocessing
- **Indices:** Speed up queries by market and time
- **Status table:** Track where you left off, handle restarts gracefully
- **Separate metrics table:** Don't recompute from scratch; just append new rows

---

## Step 3: Data Ingestion Service (Python)

Create a robust ingestion script. Here's a complete example:

### Install Dependencies

```bash
pip install injective-py psycopg2-binary pandas numpy python-dotenv
```

### Full Ingestion Service

```python
# ingest_service.py
import asyncio
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import psycopg2
import psycopg2.extras
import logging
from pyinjective.client import Client
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ingest.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# Database config
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "volatility_api")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "postgres")

# Injective config
INJECTIVE_NETWORK = os.getenv("INJECTIVE_NETWORK", "mainnet")
CANDLE_RESOLUTION = 3600  # 1 hour (in seconds)

def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

async def fetch_market_list(client):
    """Get all active markets from Injective"""
    try:
        markets = await client.get_exchange_markets()
        logger.info(f"Found {len(markets)} markets")
        return markets
    except Exception as e:
        logger.error(f"Failed to fetch markets: {e}")
        return []

async def fetch_candles(client, market_id, resolution, limit=100):
    """
    Fetch historical candles from Injective
    
    Args:
        market_id: Market identifier
        resolution: Candle size in seconds (e.g., 3600 for 1h)
        limit: Number of candles to fetch
    """
    try:
        candles = await client.get_historical_candles(
            market_id=market_id,
            resolution=resolution,
            limit=limit
        )
        logger.debug(f"Fetched {len(candles)} candles for {market_id}")
        return candles
    except Exception as e:
        logger.error(f"Failed to fetch candles for {market_id}: {e}")
        return []

def insert_candles(conn, market_id, resolution, candles):
    """
    Insert or update candles in database
    Uses INSERT ... ON CONFLICT to handle duplicates gracefully
    """
    if not candles:
        return 0
    
    cursor = conn.cursor()
    inserted = 0
    
    try:
        for candle in candles:
            cursor.execute("""
                INSERT INTO candles 
                (market_id, resolution, timestamp, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (market_id, resolution, timestamp) 
                DO UPDATE SET
                    close = EXCLUDED.close,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    volume = EXCLUDED.volume
            """, (
                market_id,
                resolution,
                int(candle['timestamp'] / 1000),  # Convert ms to seconds if needed
                float(candle['open']),
                float(candle['high']),
                float(candle['low']),
                float(candle['close']),
                float(candle['volume'])
            ))
            inserted += 1
        
        conn.commit()
        logger.info(f"Inserted {inserted} candles for {market_id}")
        return inserted
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting candles: {e}")
        return 0
    finally:
        cursor.close()

def get_last_candle_timestamp(conn, market_id, resolution):
    """Get the timestamp of the last candle we have for a market"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT MAX(timestamp) 
            FROM candles 
            WHERE market_id = %s AND resolution = %s
        """, (market_id, resolution))
        
        result = cursor.fetchone()
        last_ts = result[0] if result and result[0] else None
        return last_ts
        
    finally:
        cursor.close()

async def ingest_market_data(client, market_id):
    """
    Ingest data for a single market
    Fetches missing candles and stores them
    """
    conn = get_db_connection()
    
    try:
        # Get last candle we have
        last_ts = get_last_candle_timestamp(conn, market_id, CANDLE_RESOLUTION)
        
        # Fetch fresh candles
        candles = await fetch_candles(
            client, 
            market_id, 
            CANDLE_RESOLUTION,
            limit=200  # Get last 200 candles
        )
        
        if candles:
            # Insert into database
            inserted = insert_candles(
                conn,
                market_id,
                CANDLE_RESOLUTION,
                candles
            )
            
            logger.info(
                f"Market {market_id}: Last known timestamp = {last_ts}, "
                f"New candles inserted = {inserted}"
            )
            
            return inserted > 0
        
        return False
        
    except Exception as e:
        logger.error(f"Error ingesting data for {market_id}: {e}")
        return False
    finally:
        conn.close()

async def main_loop():
    """
    Main ingestion loop
    Runs continuously, refreshing data every N minutes
    """
    client = Client(network=INJECTIVE_NETWORK)
    
    logger.info(f"Starting data ingestion service ({INJECTIVE_NETWORK})")
    
    iteration = 0
    while True:
        iteration += 1
        logger.info(f"=== Ingestion iteration {iteration} ===")
        start_time = time.time()
        
        try:
            # Get list of markets (refresh every hour)
            if iteration % 60 == 1:
                markets = await fetch_market_list(client)
                market_ids = [m['market_id'] for m in markets]
            
            # Ingest data for top markets (limit to avoid rate limits)
            top_markets = market_ids[:20]  # Adjust as needed
            
            success_count = 0
            for market_id in top_markets:
                if await ingest_market_data(client, market_id):
                    success_count += 1
                # Add small delay to avoid rate limiting
                await asyncio.sleep(0.5)
            
            elapsed = time.time() - start_time
            logger.info(
                f"Iteration {iteration} complete: "
                f"{success_count}/{len(top_markets)} markets updated in {elapsed:.1f}s"
            )
            
        except Exception as e:
            logger.error(f"Iteration {iteration} failed: {e}")
        
        # Wait before next iteration (5 minutes)
        logger.info("Waiting 5 minutes until next iteration...")
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main_loop())
```

### Environment File (.env)

```bash
# .env
DB_HOST=localhost
DB_NAME=volatility_api
DB_USER=postgres
DB_PASS=your_password
INJECTIVE_NETWORK=mainnet
```

---

## Step 4: Volatility Computation Service

Once you have candle data, compute metrics:

```python
# compute_metrics.py
import numpy as np
import pandas as pd
import psycopg2
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def calculate_realized_volatility(returns, window=20):
    """
    Calculate realized volatility (annualized standard deviation of returns)
    
    Args:
        returns: Array of log returns
        window: Rolling window size
    
    Returns:
        Array of volatility values
    """
    if len(returns) < window:
        return np.full(len(returns), np.nan)
    
    # Annualize: sqrt(252) for daily returns, sqrt(252*24) for hourly
    rolling_std = pd.Series(returns).rolling(window=window).std()
    volatility = rolling_std * np.sqrt(252 * 24)  # Annualized for hourly data
    
    return volatility.values

def calculate_bollinger_bands(prices, window=20, num_std=2):
    """Calculate Bollinger Bands"""
    sma = pd.Series(prices).rolling(window=window).mean()
    std = pd.Series(prices).rolling(window=window).std()
    
    upper_band = sma + (num_std * std)
    lower_band = sma - (num_std * std)
    
    return upper_band.values, sma.values, lower_band.values

def calculate_atr(high, low, close, window=14):
    """Calculate Average True Range"""
    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))
    
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    atr = pd.Series(tr).rolling(window=window).mean()
    
    return atr.values

def calculate_momentum(prices, window=12):
    """Calculate Price Momentum (ROC)"""
    momentum = np.diff(prices, n=window) / np.roll(prices, window)[window:]
    return momentum

def compute_metrics_for_market(conn, market_id, limit=500):
    """
    Compute volatility metrics for a market
    Reads candle data, calculates metrics, writes to metrics table
    """
    cursor = conn.cursor()
    
    try:
        # Fetch recent candles
        cursor.execute("""
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE market_id = %s AND resolution = 3600
            ORDER BY timestamp DESC
            LIMIT %s
        """, (market_id, limit))
        
        rows = cursor.fetchall()
        
        if len(rows) < 30:
            logger.warning(f"Not enough candles for {market_id}: {len(rows)}")
            return
        
        # Reverse to chronological order
        rows = list(reversed(rows))
        
        # Extract data
        timestamps = np.array([r[0] for r in rows])
        opens = np.array([float(r[1]) for r in rows])
        highs = np.array([float(r[2]) for r in rows])
        lows = np.array([float(r[3]) for r in rows])
        closes = np.array([float(r[4]) for r in rows])
        volumes = np.array([float(r[5]) for r in rows])
        
        # Calculate returns
        log_returns = np.diff(np.log(closes))
        
        # Calculate metrics
        vol_1h = calculate_realized_volatility(log_returns, window=1)[-1]
        vol_4h = calculate_realized_volatility(log_returns, window=4)[-1]
        vol_24h = calculate_realized_volatility(log_returns, window=24)[-1]
        
        bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(closes, window=20)
        atr = calculate_atr(highs, lows, closes, window=14)
        momentum = calculate_momentum(closes, window=12)
        
        # Use last values
        last_timestamp = timestamps[-1]
        
        cursor.execute("""
            INSERT INTO volatility_metrics
            (market_id, timestamp, volatility_1h, volatility_4h, volatility_24h,
             bb_upper, bb_middle, bb_lower, atr, momentum)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (market_id, timestamp) 
            DO UPDATE SET
                volatility_1h = EXCLUDED.volatility_1h,
                volatility_4h = EXCLUDED.volatility_4h,
                volatility_24h = EXCLUDED.volatility_24h,
                bb_upper = EXCLUDED.bb_upper,
                bb_middle = EXCLUDED.bb_middle,
                bb_lower = EXCLUDED.bb_lower,
                atr = EXCLUDED.atr,
                momentum = EXCLUDED.momentum
        """, (
            market_id,
            last_timestamp,
            float(vol_1h) if not np.isnan(vol_1h) else None,
            float(vol_4h) if not np.isnan(vol_4h) else None,
            float(vol_24h) if not np.isnan(vol_24h) else None,
            float(bb_upper[-1]) if not np.isnan(bb_upper[-1]) else None,
            float(bb_mid[-1]) if not np.isnan(bb_mid[-1]) else None,
            float(bb_lower[-1]) if not np.isnan(bb_lower[-1]) else None,
            float(atr[-1]) if not np.isnan(atr[-1]) else None,
            float(momentum[-1]) if not np.isnan(momentum[-1]) else None
        ))
        
        conn.commit()
        logger.info(f"Computed metrics for {market_id} at {last_timestamp}")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error computing metrics for {market_id}: {e}")
    finally:
        cursor.close()
```

---

## Step 5: Deployment & Running

### Option A: Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: secure_password
      POSTGRES_DB: volatility_api
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  ingest:
    build: .
    depends_on:
      - postgres
    environment:
      DB_HOST: postgres
      DB_USER: postgres
      DB_PASS: secure_password
      INJECTIVE_NETWORK: mainnet
    command: python ingest_service.py
    restart: always

  compute:
    build: .
    depends_on:
      - postgres
    environment:
      DB_HOST: postgres
      DB_USER: postgres
      DB_PASS: secure_password
    command: python compute_service.py  # Runs metrics computation on schedule
    restart: always

volumes:
  postgres_data:
```

### Option B: Systemd Service (Linux)

Create `/etc/systemd/system/volatility-ingest.service`:

```ini
[Unit]
Description=Volatility Indicators Data Ingestion
After=network.target postgresql.service

[Service]
Type=simple
User=volatility
WorkingDirectory=/home/volatility/api
Environment="PATH=/home/volatility/api/.venv/bin"
ExecStart=/home/volatility/api/.venv/bin/python ingest_service.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then run:
```bash
sudo systemctl enable volatility-ingest
sudo systemctl start volatility-ingest
sudo systemctl status volatility-ingest
```

---

## Step 6: Monitoring & Validation

### Health Check Script

```python
# health_check.py
import psycopg2
import logging
from datetime import datetime, timedelta

def check_pipeline_health():
    """Check if data pipeline is healthy"""
    conn = psycopg2.connect(...)
    cursor = conn.cursor()
    
    checks = {
        "database": False,
        "recent_candles": False,
        "recent_metrics": False,
        "candle_count": 0
    }
    
    try:
        # Check DB connection
        cursor.execute("SELECT 1")
        checks["database"] = True
        
        # Check for recent candles (within last 5 minutes)
        cursor.execute("""
            SELECT COUNT(*) 
            FROM candles 
            WHERE timestamp > (EXTRACT(EPOCH FROM now()) - 300)
        """)
        candle_count = cursor.fetchone()[0]
        checks["recent_candles"] = candle_count > 0
        checks["candle_count"] = candle_count
        
        # Check for recent metrics
        cursor.execute("""
            SELECT COUNT(*) 
            FROM volatility_metrics 
            WHERE timestamp > (EXTRACT(EPOCH FROM now()) - 600)
        """)
        metrics_count = cursor.fetchone()[0]
        checks["recent_metrics"] = metrics_count > 0
        
        print("Pipeline Health Check:")
        print(f"  Database: {'✓' if checks['database'] else '✗'}")
        print(f"  Recent candles: {'✓' if checks['recent_candles'] else '✗'} ({checks['candle_count']} in last 5 min)")
        print(f"  Recent metrics: {'✓' if checks['recent_metrics'] else '✗'}")
        
        return all(checks.values())
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    health_ok = check_pipeline_health()
    exit(0 if health_ok else 1)
```

---

## Troubleshooting

### Issue: "Unable to connect to Injective API"
- Check network connectivity: `curl -s https://mainnet-api.injective.network/api/exchange/v1/markets`
- Check rate limits: Add exponential backoff in your retry logic
- Use testnet if mainnet has issues: `INJECTIVE_NETWORK=testnet`

### Issue: "Duplicate candles or gaps in data"
- The schema uses `ON CONFLICT` to handle this
- Check logs for network timeouts
- Increase `limit` in `fetch_candles()` to backfill missing data

### Issue: "Metrics computation is slow"
- Add indices on candles table: `CREATE INDEX idx_market_ts ON candles(market_id, timestamp DESC)`
- Use batch processing for multiple markets
- Cache intermediate results in Redis

---

## Next Steps

Once data pipeline is stable:

1. **Build the API server** (FastAPI/Express) to query metrics
2. **Add Redis caching** for sub-second queries
3. **Implement WebSocket subscriptions** for real-time updates
4. **Write comprehensive tests** with mock data
5. **Set up monitoring** (Prometheus, Grafana, or similar)

This pipeline gives you a solid foundation. You're ready to build the actual API!
