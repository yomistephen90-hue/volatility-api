# API Testing & Deployment Guide

## Testing the API Locally

### 1. Start the API Server

```bash
# Make sure PostgreSQL is running and has data
python api_server.py

# Or using uvicorn directly:
uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### 2. Test Health Endpoint

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-29T10:15:23.456Z",
  "version": "1.0.0",
  "database": "connected"
}
```

### 3. View Interactive Documentation

Open in browser: **http://localhost:8000/api/docs**

This gives you:
- Full endpoint documentation
- Try-it-out functionality
- Request/response examples
- Schema definitions

### 4. Run Manual Tests

#### Test single market query:
```bash
# INJ/USDT market
curl http://localhost:8000/api/volatility/0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70
```

#### Test batch query:
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

#### Test ranking:
```bash
curl "http://localhost:8000/api/markets/volatility/ranking?limit=10&sort=desc"
```

#### Test history:
```bash
curl "http://localhost:8000/api/volatility/0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70/history?days=7"
```

---

## Automated Testing

### Create `test_api.py`:

```python
import pytest
import requests
from datetime import datetime

BASE_URL = "http://localhost:8000"

# Test market IDs
INJ_USDT = "0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70"
BTC_USDT = "0x17ef48032cb9375375e6c2873b92f5837f48f5cbee62e4db0cf076fa368e3e5d"

class TestHealth:
    """Test health and status endpoints"""
    
    def test_health_check(self):
        """API should be healthy"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
    
    def test_api_status(self):
        """Should return API status"""
        response = requests.get(f"{BASE_URL}/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "api_version" in data
        assert "tracked_markets" in data
        assert data["tracked_markets"] > 0


class TestVolatilityEndpoints:
    """Test volatility metric endpoints"""
    
    def test_single_market_volatility(self):
        """Get volatility for single market"""
        response = requests.get(
            f"{BASE_URL}/api/volatility/{INJ_USDT}"
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["market_id"] == INJ_USDT
        assert "timestamp" in data
        assert "metrics" in data
        
        metrics = data["metrics"]
        assert "volatility_24h" in metrics
        assert "bollinger_bands" in metrics
        assert "atr" in metrics
        assert "momentum" in metrics
    
    def test_batch_query(self):
        """Get volatility for multiple markets at once"""
        response = requests.post(
            f"{BASE_URL}/api/volatility/batch",
            json={"market_ids": [INJ_USDT, BTC_USDT]}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 2
        
        for market in data:
            assert "market_id" in market
            assert "timestamp" in market
            assert "metrics" in market
    
    def test_batch_empty_markets(self):
        """Batch query with empty list should return empty list"""
        response = requests.post(
            f"{BASE_URL}/api/volatility/batch",
            json={"market_ids": []}
        )
        assert response.status_code == 200
        data = response.json()
        assert data == []
    
    def test_market_not_found(self):
        """Should return 404 for non-existent market"""
        response = requests.get(
            f"{BASE_URL}/api/volatility/0x0000000000000000000000000000000000000000"
        )
        assert response.status_code == 404
    
    def test_volatility_values_valid(self):
        """Volatility values should be reasonable"""
        response = requests.get(
            f"{BASE_URL}/api/volatility/{INJ_USDT}"
        )
        data = response.json()
        metrics = data["metrics"]
        
        # Volatility should be between 0 and 1 (0% to 100%)
        if metrics["volatility_24h"] is not None:
            assert 0 <= metrics["volatility_24h"] <= 1
        
        # Bollinger bands should be in reasonable range
        bb = metrics["bollinger_bands"]
        if all([bb["upper"], bb["middle"], bb["lower"]]):
            assert bb["lower"] <= bb["middle"] <= bb["upper"]


class TestHistoricalData:
    """Test historical data endpoints"""
    
    def test_history_default_days(self):
        """Get default 7 days of history"""
        response = requests.get(
            f"{BASE_URL}/api/volatility/{INJ_USDT}/history"
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["market_id"] == INJ_USDT
        assert "history" in data
        assert len(data["history"]) > 0
    
    def test_history_custom_days(self):
        """Get custom days of history"""
        for days in [1, 7, 30, 90]:
            response = requests.get(
                f"{BASE_URL}/api/volatility/{INJ_USDT}/history",
                params={"days": days}
            )
            assert response.status_code == 200
            data = response.json()
            assert "history" in data
    
    def test_history_invalid_days(self):
        """Should reject invalid day ranges"""
        response = requests.get(
            f"{BASE_URL}/api/volatility/{INJ_USDT}/history",
            params={"days": 200}  # > 90 max
        )
        # Should either return 422 (validation error) or cap at 90
        assert response.status_code in [200, 422]
    
    def test_history_chronological_order(self):
        """History should be in chronological order (oldest first)"""
        response = requests.get(
            f"{BASE_URL}/api/volatility/{INJ_USDT}/history?days=7"
        )
        data = response.json()
        history = data["history"]
        
        if len(history) > 1:
            for i in range(len(history) - 1):
                assert history[i]["timestamp"] <= history[i+1]["timestamp"]


class TestRanking:
    """Test market ranking endpoints"""
    
    def test_ranking_default(self):
        """Get top 10 markets by volatility"""
        response = requests.get(
            f"{BASE_URL}/api/markets/volatility/ranking"
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 10
        
        for i, market in enumerate(data):
            assert market["rank"] == i + 1
            assert "market_id" in market
            assert "volatility_24h" in market
    
    def test_ranking_custom_limit(self):
        """Get custom number of markets"""
        response = requests.get(
            f"{BASE_URL}/api/markets/volatility/ranking?limit=20"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 20
    
    def test_ranking_sort_ascending(self):
        """Test ascending sort (lowest vol first)"""
        response = requests.get(
            f"{BASE_URL}/api/markets/volatility/ranking?limit=10&sort=asc"
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should be sorted in ascending order
        for i in range(len(data) - 1):
            vol1 = data[i].get("volatility_24h") or 0
            vol2 = data[i+1].get("volatility_24h") or 0
            assert vol1 <= vol2
    
    def test_ranking_sort_descending(self):
        """Test descending sort (highest vol first)"""
        response = requests.get(
            f"{BASE_URL}/api/markets/volatility/ranking?limit=10&sort=desc"
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should be sorted in descending order
        for i in range(len(data) - 1):
            vol1 = data[i].get("volatility_24h") or 0
            vol2 = data[i+1].get("volatility_24h") or 0
            assert vol1 >= vol2


class TestResponseFormat:
    """Test response format and error handling"""
    
    def test_response_has_proper_headers(self):
        """Responses should have proper headers"""
        response = requests.get(
            f"{BASE_URL}/api/volatility/{INJ_USDT}"
        )
        assert response.headers["Content-Type"] == "application/json"
    
    def test_error_response_format(self):
        """Error responses should have consistent format"""
        response = requests.get(
            f"{BASE_URL}/api/volatility/0x0000000000000000000000000000000000000000"
        )
        assert response.status_code == 404
        
        data = response.json()
        assert "error" in data
        assert "timestamp" in data


class TestPerformance:
    """Test API performance"""
    
    def test_single_query_response_time(self):
        """Single market query should be fast"""
        import time
        start = time.time()
        response = requests.get(
            f"{BASE_URL}/api/volatility/{INJ_USDT}"
        )
        elapsed = time.time() - start
        
        assert response.status_code == 200
        assert elapsed < 0.5  # Should be under 500ms
    
    def test_batch_query_response_time(self):
        """Batch query should be efficient"""
        import time
        start = time.time()
        response = requests.post(
            f"{BASE_URL}/api/volatility/batch",
            json={"market_ids": [INJ_USDT, BTC_USDT]}
        )
        elapsed = time.time() - start
        
        assert response.status_code == 200
        assert elapsed < 1.0  # Should be under 1 second


if __name__ == "__main__":
    # Run tests with: pytest test_api.py -v
    print("Run with: pytest test_api.py -v")
```

### Run tests:

```bash
# Install pytest
pip install pytest pytest-cov

# Run all tests
pytest test_api.py -v

# Run specific test class
pytest test_api.py::TestVolatilityEndpoints -v

# With coverage report
pytest test_api.py --cov=api_server --cov-report=html
```

---

## Deployment

### Option 1: Railway.app (Recommended for Contest)

#### Setup (5 minutes):

1. **Create Railway account** at https://railway.app
2. **Connect GitHub** (or use CLI)
3. **Create PostgreSQL plugin**:
   - Click "Create" → "Database" → PostgreSQL
   - Copy connection string
4. **Create Python service**:
   - Click "Create" → "GitHub Repo" (or upload code)
   - Set start command: `uvicorn api_server:app --host 0.0.0.0 --port $PORT`
5. **Add environment variables**:
   ```
   DB_HOST=<from PostgreSQL>
   DB_NAME=volatility_api
   DB_USER=<from PostgreSQL>
   DB_PASS=<from PostgreSQL>
   DB_PORT=5432
   DEBUG=False
   ```
6. **Deploy** - Railway auto-deploys on push

Your API will be live at: `https://your-project.railway.app`

---

### Option 2: Heroku

```bash
# Install Heroku CLI
curl https://cli-assets.heroku.com/install.sh | sh

# Login
heroku login

# Create app
heroku create volatility-api

# Add PostgreSQL
heroku addons:create heroku-postgresql:hobby-dev

# Set environment variables
heroku config:set DEBUG=False

# Deploy (if using Git)
git push heroku main

# View logs
heroku logs --tail
```

---

### Option 3: Docker (Self-Hosted)

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api_server.py .
COPY quick_start_ingest.py .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: volatility
      POSTGRES_PASSWORD: secure_password
      POSTGRES_DB: volatility_api
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      DB_HOST: postgres
      DB_NAME: volatility_api
      DB_USER: volatility
      DB_PASS: secure_password
      DEBUG: "False"
    depends_on:
      - postgres
    restart: always

volumes:
  postgres_data:
```

Run:
```bash
docker-compose up -d
# API available at http://localhost:8000
```

---

## Monitoring in Production

### Set up logging:

```python
# Add to api_server.py
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler('api.log', maxBytes=10485760, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
```

### Monitor health:

```bash
# Every 5 minutes, check API health
*/5 * * * * curl -s https://volatility-api.example.com/health >> /var/log/api-health.log 2>&1
```

### Monitor database:

```bash
# Check data freshness
psql volatility_api volatility -c "
  SELECT 
    COUNT(*) as metric_count,
    MAX(timestamp) as latest_timestamp,
    NOW() - to_timestamp(MAX(timestamp)) as age_seconds
  FROM volatility_metrics;
"
```

---

## Production Checklist

Before going live:

- [ ] All tests passing
- [ ] Environment variables set correctly
- [ ] Database backups configured
- [ ] Logging enabled
- [ ] Error monitoring setup (e.g., Sentry)
- [ ] Rate limiting configured
- [ ] CORS properly set (not `["*"]` in prod)
- [ ] API documentation deployed
- [ ] Monitoring alerts configured
- [ ] Load testing done

---

## Load Testing

```bash
# Install Apache Bench or wrk
# Using Apache Bench:
ab -n 1000 -c 100 http://localhost:8000/api/volatility/0xa508cb...

# Or with wrk (better for concurrent testing):
wrk -t4 -c100 -d30s http://localhost:8000/api/volatility/0xa508cb...
```

Expected results:
- Requests/sec: > 100
- P99 latency: < 500ms
- Error rate: 0%

---

## Continuous Deployment

### GitHub Actions Example:

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Railway

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Run tests
        run: |
          pip install -r requirements.txt
          pytest test_api.py
      
      - name: Deploy to Railway
        run: |
          npm i -g @railway/cli
          railway up
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
```

---

## Troubleshooting

### "Connection refused" error

```bash
# Check if server is running
curl http://localhost:8000/health

# Check database connection
python -c "
import psycopg2
conn = psycopg2.connect(host='localhost', database='volatility_api', user='volatility', password='pass')
print('✓ Database connected')
"
```

### "No metrics available" error

Ensure:
1. Data ingestion is running: `python quick_start_ingest.py`
2. Database has tables: `psql volatility_api volatility -c "\dt"`
3. Wait a few minutes for metrics to be computed

### High latency

- Check database query performance
- Add caching layer (Redis)
- Enable gzip compression
- Consider read replicas

---

Done! Your API is production-ready. 🚀
