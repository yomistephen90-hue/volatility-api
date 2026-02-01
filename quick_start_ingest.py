#!/usr/bin/env python3
"""
Quick-start data ingestion for Volatility Indicators API
Minimal version to get you running fast
"""

import asyncio
import os
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras
import logging
from typing import List, Dict
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "volatility_api"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASS", "postgres"),
    "port": os.getenv("DB_PORT", "5432")
}

# For this MVP, we'll use public REST API
# In production, use the Python SDK: pip install injective-py
INJECTIVE_API_BASE = "https://mainnet-api.injective.network"

# Test markets (you can expand this)
TEST_MARKETS = [
    "0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70",  # INJ/USDT
    "0x17ef48032cb9375375e6c2873b92f5837f48f5cbee62e4db0cf076fa368e3e5d",  # BTC/USDT
    "0xca51c18b48c2d7fda3e6b5a40491876ca06c39f6984152e44fcb4c4a3e4f25e5",  # ETH/USDT
]

# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def init_database():
    """Create tables if they don't exist"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        # Candles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candles (
                id BIGSERIAL PRIMARY KEY,
                market_id VARCHAR(255) NOT NULL,
                resolution INT NOT NULL,
                timestamp BIGINT NOT NULL,
                open NUMERIC(20, 8) NOT NULL,
                high NUMERIC(20, 8) NOT NULL,
                low NUMERIC(20, 8) NOT NULL,
                close NUMERIC(20, 8) NOT NULL,
                volume NUMERIC(20, 8) NOT NULL,
                
                UNIQUE(market_id, resolution, timestamp)
            );
        """)
        
        # Create index for fast queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_time 
            ON candles (market_id, timestamp DESC);
        """)
        
        # Metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS volatility_metrics (
                id BIGSERIAL PRIMARY KEY,
                market_id VARCHAR(255) NOT NULL,
                timestamp BIGINT NOT NULL,
                volatility_24h NUMERIC(10, 6),
                bb_upper NUMERIC(20, 8),
                bb_middle NUMERIC(20, 8),
                bb_lower NUMERIC(20, 8),
                atr NUMERIC(20, 8),
                momentum NUMERIC(10, 6),
                
                UNIQUE(market_id, timestamp)
            );
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_market_time 
            ON volatility_metrics (market_id, timestamp DESC);
        """)
        
        conn.commit()
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def insert_candle(market_id: str, resolution: int, candle_data: Dict):
    """Insert a single candle into the database"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO candles 
            (market_id, resolution, timestamp, open, high, low, close, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (market_id, resolution, timestamp) 
            DO UPDATE SET close = EXCLUDED.close
        """, (
            market_id,
            resolution,
            int(candle_data['timestamp']),
            float(candle_data['open']),
            float(candle_data['high']),
            float(candle_data['low']),
            float(candle_data['close']),
            float(candle_data['volume'])
        ))
        conn.commit()
        
    except Exception as e:
        logger.error(f"Error inserting candle: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def get_recent_candles(market_id: str, limit: int = 50) -> List[Dict]:
    """Fetch recent candles for a market"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cursor.execute("""
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE market_id = %s AND resolution = 3600
            ORDER BY timestamp DESC
            LIMIT %s
        """, (market_id, limit))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
        
    finally:
        cursor.close()
        conn.close()

# ============================================================================
# API INGESTION (Using REST)
# ============================================================================

async def fetch_candles_rest(market_id: str, resolution: int = 3600, limit: int = 100):
    """
    Fetch candles from Injective REST API
    
    Note: For production, use the official Injective Python SDK instead
    For now, this is a placeholder showing the concept
    """
    import aiohttp
    
    url = f"{INJECTIVE_API_BASE}/api/exchange/v1/historical_candles"
    params = {
        "marketId": market_id,
        "resolution": resolution,
        "limit": limit
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Fetched {len(data.get('candles', []))} candles for {market_id}")
                    return data.get('candles', [])
                else:
                    logger.error(f"API returned {resp.status}")
                    return []
    except Exception as e:
        logger.error(f"Error fetching candles: {e}")
        return []

# ============================================================================
# VOLATILITY COMPUTATION
# ============================================================================

import numpy as np
import pandas as pd

def compute_volatility_metrics(candles: List[Dict]) -> Dict:
    """
    Compute volatility metrics from candle data
    
    Input: List of candles with OHLCV data
    Output: Dict with volatility metrics
    """
    if len(candles) < 30:
        logger.warning(f"Not enough candles ({len(candles)}) for metrics computation")
        return {}
    
    try:
        # Convert to numpy arrays
        closes = np.array([float(c['close']) for c in candles])
        highs = np.array([float(c['high']) for c in candles])
        lows = np.array([float(c['low']) for c in candles])
        
        # Calculate log returns
        log_returns = np.diff(np.log(closes))
        
        # 24-hour volatility (last 24 hours = 24 hourly candles)
        vol_24h = np.std(log_returns[-24:]) * np.sqrt(252) if len(log_returns) >= 24 else np.nan
        
        # Bollinger Bands (20-period, 2 std dev)
        window = 20
        if len(closes) >= window:
            sma = pd.Series(closes).rolling(window=window).mean()
            std = pd.Series(closes).rolling(window=window).std()
            bb_upper = sma + (2 * std)
            bb_lower = sma - (2 * std)
            
            bb_upper_val = float(bb_upper.iloc[-1])
            bb_middle_val = float(sma.iloc[-1])
            bb_lower_val = float(bb_lower.iloc[-1])
        else:
            bb_upper_val = bb_middle_val = bb_lower_val = np.nan
        
        # ATR (Average True Range)
        tr = np.maximum(
            highs - lows,
            np.maximum(
                np.abs(highs - np.roll(closes, 1)),
                np.abs(lows - np.roll(closes, 1))
            )
        )
        atr = np.mean(tr[-14:]) if len(tr) >= 14 else np.nan
        
        # Momentum (12-period price change)
        momentum = (closes[-1] - closes[-12]) / closes[-12] if len(closes) >= 12 else np.nan
        
        return {
            "volatility_24h": float(vol_24h) if not np.isnan(vol_24h) else None,
            "bb_upper": float(bb_upper_val) if not np.isnan(bb_upper_val) else None,
            "bb_middle": float(bb_middle_val) if not np.isnan(bb_middle_val) else None,
            "bb_lower": float(bb_lower_val) if not np.isnan(bb_lower_val) else None,
            "atr": float(atr) if not np.isnan(atr) else None,
            "momentum": float(momentum) if not np.isnan(momentum) else None,
        }
        
    except Exception as e:
        logger.error(f"Error computing metrics: {e}")
        return {}

def insert_metrics(market_id: str, timestamp: int, metrics: Dict):
    """Store computed metrics"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO volatility_metrics
            (market_id, timestamp, volatility_24h, bb_upper, bb_middle, bb_lower, atr, momentum)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (market_id, timestamp) DO UPDATE SET volatility_24h = EXCLUDED.volatility_24h
        """, (
            market_id,
            timestamp,
            metrics.get('volatility_24h'),
            metrics.get('bb_upper'),
            metrics.get('bb_middle'),
            metrics.get('bb_lower'),
            metrics.get('atr'),
            metrics.get('momentum')
        ))
        conn.commit()
        logger.info(f"Inserted metrics for {market_id} at {timestamp}")
        
    except Exception as e:
        logger.error(f"Error inserting metrics: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

# ============================================================================
# MAIN PIPELINE
# ============================================================================

async def process_market(market_id: str):
    """
    Process a single market:
    1. Fetch candles
    2. Store in DB
    3. Compute metrics
    4. Store metrics
    """
    logger.info(f"Processing market: {market_id}")
    
    # Fetch candles
    candles = await fetch_candles_rest(market_id, limit=100)
    
    if not candles:
        logger.warning(f"No candles fetched for {market_id}")
        return
    
    # Insert candles
    for candle in candles:
        insert_candle(market_id, 3600, candle)
    
    logger.info(f"Inserted {len(candles)} candles")
    
    # Compute metrics from recent candles
    recent = get_recent_candles(market_id, limit=50)
    
    if recent:
        metrics = compute_volatility_metrics(recent)
        
        if metrics:
            # Use the timestamp of the last candle
            last_timestamp = recent[0]['timestamp']
            insert_metrics(market_id, last_timestamp, metrics)
            logger.info(f"Metrics computed: {json.dumps(metrics, indent=2)}")

async def main():
    """Main entry point"""
    logger.info("Starting Volatility Indicators Data Pipeline")
    
    # Initialize database
    init_database()
    
    logger.info(f"Configured to use database: {DB_CONFIG['database']}")
    logger.info(f"Test markets: {len(TEST_MARKETS)}")
    
    # Process markets
    for market_id in TEST_MARKETS:
        try:
            await process_market(market_id)
        except Exception as e:
            logger.error(f"Error processing {market_id}: {e}")
        
        # Small delay to avoid rate limiting
        await asyncio.sleep(1)
    
    logger.info("Pipeline run complete")

if __name__ == "__main__":
    # Install dependencies first:
    # pip install psycopg2-binary aiohttp python-dotenv numpy pandas
    
    asyncio.run(main())
