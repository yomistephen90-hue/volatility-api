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
# Install all dependencies
pip install -r requirements.txt
```

**requirements.txt includes:**
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
  1. Go to https://railway.app and create an account
  2. Create a new PostgreSQL database
  3. Copy the connection string from Dashboard
  4. Add to `.env`:
```
     DB_HOST=your-railway-host.railway.app
     DB_PORT=5432
     DB_NAME=your_database_name
     DB_USER=postgres
     DB_PASS=your_password
```

- **Supabase** (PostgreSQL + built-in tools)
  1. Go to https://supabase.com and create an account
  2. Create a new project and PostgreSQL database
  3. Go to Settings → Database → Connection String
  4. Copy the connection info and add to `.env`
  5. Replace `[YOUR-PASSWORD]` with your actual password

- **Heroku PostgreSQL** (Alternative)
  1. Go to https://heroku.com and create an account
  2. Create a new app
  3. Add PostgreSQL add-on (Hobby tier is free)
  4. Copy DATABASE_URL from Config Vars
  5. Add to `.env`

     
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
2. Fetch candles for test markets
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

## Running the API Server

Start the API with:
```bash
python api_server.py
```

Or with uvicorn directly:
```bash
uvicorn api_server:app --reload
```

The API will be available at: **http://localhost:8000**

### Access Interactive Docs
```bash
# Swagger UI
open http://localhost:8000/api/docs

# ReDoc (alternative documentation)
open http://localhost:8000/api/redoc
```

### Test a Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2026-01-29T10:15:23Z"
}
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

### "Connection refused" on database connection

Make sure PostgreSQL is running:
```bash
# macOS
brew services start postgresql

# Linux
sudo systemctl start postgresql

# Windows
# Check Services app or use pgAdmin
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

## Testing API Endpoints

### Get Market Volatility
```bash
curl http://localhost:8000/api/volatility/0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70
```

### Batch Query Multiple Markets
```bash
curl -X POST http://localhost:8000/api/volatility/batch \
  -H "Content-Type: application/json" \
  -d '{
    "market_ids": [
      "0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70",
      "0x17ef48032cb9375375e6c2873b92f5837f48f5cbee62e4db0cf076fa368e3e5d"
    ]
  }'
```

### Get Market Ranking
```bash
curl http://localhost:8000/api/markets/volatility/ranking?limit=10&sort=desc
```

### Get Historical Data
```bash
curl "http://localhost:8000/api/volatility/0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70/history?days=7"
```

---

## Next Steps

Once everything is running:

1. **Read API documentation:** [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
2. **Learn the architecture:** [data_pipeline_setup.md](data_pipeline_setup.md)
3. **Deploy to production:** [TESTING_DEPLOYMENT.md](TESTING_DEPLOYMENT.md)
4. **Integrate with your app:** See JavaScript/Python examples in README

---

## Support

Stuck? Check:
1. `.env` file has correct values
2. PostgreSQL is running: `psql -l`
3. Dependencies installed: `pip list`
4. Injective API is accessible: `curl https://mainnet-api.injective.network/api/exchange/v1/markets`
5. Check application logs for errors
6. Review common issues section above

For more help, see [API_DOCUMENTATION.md](API_DOCUMENTATION.md) or check the interactive docs at `/api/docs`

Good luck! 🚀
