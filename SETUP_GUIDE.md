# Volatility Indicators API - Setup Guide

## Prerequisites

- Python 3.9+
- PostgreSQL 12+ (local or cloud)
- Git

## Installation (5 minutes)

### 1. Clone/Setup Your Project

```bash
mkdir volatility-api
cd volatility-api

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
# Create requirements.txt with:
pip install -r requirements.txt
```

**requirements.txt:**
```
psycopg2-binary==2.9.9
aiohttp==3.9.1
python-dotenv==1.0.0
numpy==1.24.3
pandas==2.0.3
injective-py==1.30.0
fastapi==0.104.1
uvicorn==0.24.0
redis==5.0.1
```

Or install manually:
```bash
pip install psycopg2-binary aiohttp python-dotenv numpy pandas fastapi uvicorn
```

### 3. Setup PostgreSQL

**Option A: Local PostgreSQL**

```bash
# macOS with Homebrew
brew install postgresql
brew services start postgresql

# Or Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql

# Create database and user
psql postgres -c "CREATE USER volatility WITH PASSWORD 'dev_password';"
psql postgres -c "CREATE DATABASE volatility_api OWNER volatility;"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE volatility_api TO volatility;"
```

**Option B: Cloud PostgreSQL (Recommended)**

- **Railway.app** (Easy, free tier available)
  - Sign up, create PostgreSQL database
  - Copy connection string to `.env`

- **Supabase** (PostgreSQL + built-in tools)
  - Free tier includes 500 MB storage
  - Copy connection string to `.env`

### 4. Create Environment File

Create `.env` in project root:

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=volatility_api
DB_USER=volatility
DB_PASS=dev_password

# Injective
INJECTIVE_NETWORK=mainnet

# API Server
API_HOST=0.0.0.0
API_PORT=8000

# Redis (optional, for caching)
REDIS_URL=redis://localhost:6379
```

### 5. Test Database Connection

```bash
python -c "
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS')
    )
    print('✓ Database connection successful!')
    conn.close()
except Exception as e:
    print(f'✗ Connection failed: {e}')
"
```

---

## Running the Data Pipeline

### Option 1: Quick Start (One-time data fetch)

```bash
# Run the quick start script
python quick_start_ingest.py
```

This will:
1. Create tables
2. Fetch candles for 3 test markets
3. Compute volatility metrics
4. Display results

Expected output:
```
2026-01-29 10:15:23 - INFO - Starting Volatility Indicators Data Pipeline
2026-01-29 10:15:24 - INFO - Database initialized successfully
2026-01-29 10:15:24 - INFO - Processing market: 0xa508cb32923323679...
2026-01-29 10:15:25 - INFO - Fetched 100 candles for 0xa508cb32923323679...
2026-01-29 10:15:25 - INFO - Inserted 100 candles
2026-01-29 10:15:26 - INFO - Metrics computed: {...}
```

### Option 2: Continuous Ingestion (For production)

```bash
python ingest_service.py
```

This runs indefinitely, refreshing data every 5 minutes.

You can run in background:
```bash
nohup python ingest_service.py > ingest.log 2>&1 &
```

Or use `screen`:
```bash
screen -S ingest
python ingest_service.py
# Press Ctrl+A then D to detach
# screen -r ingest  # to reattach
```

---

## Verifying Data Collection

### 1. Check tables exist

```bash
psql volatility_api volatility
# In psql:
\dt
# Should show: candles, volatility_metrics, ingest_status

\q  # exit
```

### 2. Query recent candles

```bash
psql volatility_api volatility -c "
  SELECT market_id, timestamp, close, volume 
  FROM candles 
  ORDER BY timestamp DESC 
  LIMIT 5;
"
```

### 3. Check metrics

```bash
psql volatility_api volatility -c "
  SELECT market_id, timestamp, volatility_24h, atr 
  FROM volatility_metrics 
  ORDER BY timestamp DESC 
  LIMIT 5;
"
```

---

## Common Issues & Fixes

### "FATAL: database 'volatility_api' does not exist"

```bash
# Create the database
createdb -U volatility volatility_api
```

### "FATAL: password authentication failed"

Check your `.env` file - password must match what you set:

```bash
# Reset PostgreSQL password if needed
psql postgres
\password volatility
# Enter new password twice
```

### "Could not connect to Injective API"

- Check internet connection
- Try testnet: `INJECTIVE_NETWORK=testnet` in `.env`
- Check API status: `curl https://mainnet-api.injective.network/api/exchange/v1/markets`

### "ModuleNotFoundError: No module named 'psycopg2'"

```bash
# Reinstall dependencies
pip install --upgrade --force-reinstall psycopg2-binary
```

---

## Next Steps: Building the API

Once data collection is stable (you have 100+ candles per market), build the API:

### 1. Create `api_server.py`

```python
from fastapi import FastAPI
import psycopg2
from datetime import datetime
import os

app = FastAPI(title="Volatility Indicators API")

@app.get("/volatility/{market_id}")
async def get_volatility(market_id: str):
    """Get latest volatility metrics for a market"""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS")
    )
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT timestamp, volatility_24h, bb_upper, bb_middle, bb_lower, atr, momentum
            FROM volatility_metrics
            WHERE market_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (market_id,))
        
        row = cursor.fetchone()
        
        if not row:
            return {"error": "Market not found", "market_id": market_id}
        
        return {
            "market_id": market_id,
            "timestamp": row[0],
            "volatility_24h": float(row[1]) if row[1] else None,
            "bollinger_bands": {
                "upper": float(row[2]) if row[2] else None,
                "middle": float(row[3]) if row[3] else None,
                "lower": float(row[4]) if row[4] else None
            },
            "atr": float(row[5]) if row[5] else None,
            "momentum": float(row[6]) if row[6] else None
        }
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 2. Run API server

```bash
python api_server.py
# Or:
uvicorn api_server:app --reload
```

### 3. Test endpoint

```bash
curl http://localhost:8000/volatility/0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70

# Response:
{
  "market_id": "0xa508cb...",
  "timestamp": 1706419200,
  "volatility_24h": 0.0145,
  "bollinger_bands": {
    "upper": 52.40,
    "middle": 50.20,
    "lower": 48.00
  },
  "atr": 1.25,
  "momentum": 0.05
}
```

---

## Checklist Before Contest Submission

- [ ] Data pipeline runs without errors
- [ ] Database contains >100 candles per market
- [ ] Metrics are computed and stored
- [ ] API endpoints return valid data
- [ ] API documentation is clear (README, API docs)
- [ ] Error handling is robust
- [ ] Rate limiting implemented (if needed)
- [ ] Tests written (at minimum, integration tests)
- [ ] Deployment instructions provided
- [ ] Example client code (JavaScript/Python)

---

## Deployment (when ready)

### Railway.app (Recommended for contest)

```bash
# Install Railway CLI
curl -fsSL https://cli.railway.app | bash

# Login
railway login

# Create project
railway init

# Add PostgreSQL plugin
# Set env vars
# Deploy
railway up
```

### Heroku (Alternative)

```bash
# Install Heroku CLI
# Login
heroku login

# Create app
heroku create volatility-api

# Add PostgreSQL
heroku addons:create heroku-postgresql:hobby-dev

# Deploy
git push heroku main
```

---

## Monitoring

Keep tabs on your pipeline:

```bash
# Check logs
tail -f ingest.log

# Monitor database size
psql volatility_api volatility -c "
  SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
  FROM pg_tables
  WHERE schemaname = 'public'
  ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

# Check data freshness
psql volatility_api volatility -c "
  SELECT 
    market_id, 
    COUNT(*) as candle_count,
    MAX(timestamp) as latest_timestamp,
    NOW() - to_timestamp(MAX(timestamp)) as age
  FROM candles
  GROUP BY market_id
  ORDER BY MAX(timestamp) DESC;
"
```

---

## Support

Stuck? Check:
1. `.env` file has correct values
2. PostgreSQL is running: `psql -l`
3. Dependencies installed: `pip list`
4. Injective API is accessible: `curl https://mainnet-api.injective.network/api/exchange/v1/markets`
5. Check application logs

Good luck! 🚀
