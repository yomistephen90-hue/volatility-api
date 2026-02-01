# Volatility Indicators API

**A production-grade REST API for real-time volatility metrics on Injective Protocol**

![Status](https://img.shields.io/badge/status-active-success) ![Version](https://img.shields.io/badge/version-1.0.0-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## 📋 Overview

Volatility Indicators API is a complete, developer-focused infrastructure service built for the **Ninja API Forge** contest on Injective. It provides real-time volatility metrics, technical indicators, and market analysis for Injective Protocol trading pairs.

**Perfect for:**
- Trading bots and automated strategies
- Risk management dashboards
- Market analysis platforms
- Volatility-triggered alerts
- DeFi protocol integrations

---

## ✨ Key Features

### Real-Time Metrics
- **24h, 4h, 1h Volatility** - Annualized standard deviation of returns
- **Bollinger Bands** - Price bands at ±2 standard deviations
- **ATR (Average True Range)** - Volatility in price units
- **Momentum** - 12-period rate of change

### Developer-Friendly API
- Clean REST endpoints with intuitive design
- Batch queries for multiple markets
- Historical data for trend analysis
- Market ranking by volatility
- Interactive Swagger documentation
- JSON responses with proper error handling

### Production Ready
- Async data ingestion pipeline
- PostgreSQL time-series database
- Robust error handling & logging
- Health check endpoints
- Comprehensive test suite
- Docker deployment support

---

## 🚀 Quick Start (5 Minutes)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Database

```bash
# PostgreSQL (local or cloud)
# Create .env file with:
DB_HOST=localhost
DB_NAME=volatility_api
DB_USER=postgres
DB_PASS=your_password
```

### 3. Populate Data

```bash
python quick_start_ingest.py
```

### 4. Start API Server

```bash
python api_server.py
# API available at http://localhost:8000
```

### 5. Test It

```bash
# View docs
open http://localhost:8000/api/docs

# Query volatility
curl http://localhost:8000/api/volatility/0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70
```

Done! 🎉

---

## 📁 Project Structure

```
volatility-api/
├── api_server.py                    # Main FastAPI application (500+ lines)
├── quick_start_ingest.py            # One-shot data ingestion script
├── ingest_service.py                # Continuous data pipeline
├── compute_metrics.py               # Volatility calculation engine
├── test_api.py                      # Comprehensive test suite
│
├── README.md                        # This file
├── SETUP_GUIDE.md                   # Detailed setup instructions
├── API_DOCUMENTATION.md             # Complete API reference
├── TESTING_DEPLOYMENT.md            # Testing & deployment guide
├── data_pipeline_setup.md           # Technical architecture
│
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment template
├── Dockerfile                       # Docker container definition
├── docker-compose.yml               # Local development stack
│
└── README_CONTEST.md               # Contest submission notes
```

---

## 📖 Documentation

### For Setup
→ **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Installation, configuration, verification

### For API Usage
→ **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)** - All endpoints, examples, best practices

### For Development
→ **[data_pipeline_setup.md](data_pipeline_setup.md)** - Architecture, algorithms, internals

### For Deployment
→ **[TESTING_DEPLOYMENT.md](TESTING_DEPLOYMENT.md)** - Testing, production deployment, monitoring

---

## 🔌 API Endpoints

### Get Market Volatility
```bash
GET /api/volatility/{market_id}
```
Returns latest volatility metrics for a market.

### Batch Query
```bash
POST /api/volatility/batch
```
Get metrics for multiple markets efficiently.

### Historical Data
```bash
GET /api/volatility/{market_id}/history?days=7
```
Get 7-90 days of historical volatility data.

### Market Ranking
```bash
GET /api/markets/volatility/ranking?limit=10&sort=desc
```
Find high/low volatility opportunities.

### Health Check
```bash
GET /health
GET /api/status
```
Monitor API and database status.

**Full documentation:** See [API_DOCUMENTATION.md](API_DOCUMENTATION.md)

---

## 💡 Use Cases

### 1. Trading Bot
```javascript
// Find high volatility markets for day trading
const markets = await fetch('/api/markets/volatility/ranking?limit=5&sort=desc');
// Execute strategy on high vol markets
```

### 2. Risk Dashboard
```python
# Monitor portfolio volatility across markets
markets = requests.post('/api/volatility/batch', json={'market_ids': portfolio})
# Visualize volatility heatmap
```

### 3. Volatility Alert System
```bash
# Check if volatility spiked above threshold
GET /api/volatility/{market_id}
# Alert if volatility_24h > 0.10 (10%)
```

### 4. Mean Reversion Strategy
```python
# Get historical volatility
history = requests.get(f'/api/volatility/{market_id}/history?days=30')
# Find periods when volatility was low
# Enter when price moves significantly
```

---

## 🏗️ Architecture

```
┌──────────────────────┐
│  Injective API       │  Real-time market data
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Ingest Service      │  Async data collection
│  (every 5 min)       │  Error handling & retries
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  PostgreSQL DB       │  Time-series storage
│  (candles, metrics)  │  Optimized indices
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Compute Engine      │  Volatility calculations
│  (every 5 min)       │  Technical indicators
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Redis Cache         │  Fast query responses
│  (1-5 min TTL)       │  Reduces DB load
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  API Server          │  REST endpoints
│  FastAPI             │  Interactive docs
└──────────────────────┘
```

---

## 📊 Metrics Explained

### Volatility (24h, 4h, 1h)
Annualized standard deviation of log returns.

**Interpretation:**
- 0.01 (1%) = Very stable
- 0.05 (5%) = Moderate
- 0.10 (10%) = High (good for traders)
- 0.20+ (20%+) = Extreme

### Bollinger Bands
Price + Moving Average ± 2 × Standard Deviations

**Use:** Identify overbought/oversold conditions

### ATR (Average True Range)
14-period average true range in price units

**Use:** Position sizing, stop loss placement

### Momentum
12-period rate of change (-1 to +1)

**Use:** Identify trend strength

---

## 🧪 Testing

### Run Full Test Suite
```bash
pytest test_api.py -v --cov
```

### Test Coverage
- Health checks ✓
- Single market queries ✓
- Batch queries ✓
- Historical data ✓
- Market ranking ✓
- Error handling ✓
- Performance benchmarks ✓
- Response format validation ✓

---

## 🚢 Deployment

### Local Docker
```bash
docker-compose up -d
# API at http://localhost:8000
```

### Railway.app (Recommended)
```bash
# 1. Create Railway account
# 2. Connect GitHub repo
# 3. Add PostgreSQL addon
# 4. Set env variables
# 5. Deploy
# API at https://your-project.railway.app
```

### Heroku
```bash
heroku create volatility-api
heroku addons:create heroku-postgresql:hobby-dev
git push heroku main
```

### AWS / Self-Hosted
See [TESTING_DEPLOYMENT.md](TESTING_DEPLOYMENT.md) for detailed instructions.

---

## 📈 Performance

### Benchmarks
- Single query: **< 100ms** (cached)
- Batch query (10 markets): **< 200ms**
- Ranking (100 markets): **< 300ms**
- Throughput: **> 100 requests/sec**

### Optimization
- Query result caching (Redis)
- Database indices on market_id + timestamp
- Async HTTP handling
- Connection pooling

---

## 🛡️ Error Handling

All errors return consistent format:
```json
{
  "error": "Market not found",
  "details": "No data available for market 0x...",
  "timestamp": "2026-01-29T10:15:23Z"
}
```

**Common Codes:**
- 200: Success
- 404: Market not found
- 500: Server error
- 503: Database unavailable

---

## 🔧 Configuration

### Environment Variables
```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=volatility_api
DB_USER=postgres
DB_PASS=secure_password

# API Server
API_HOST=0.0.0.0
API_PORT=8000

# Redis (optional)
REDIS_URL=redis://localhost:6379

# Logging
DEBUG=False
LOG_LEVEL=INFO
```

---

## 📦 Dependencies

**Core:**
- FastAPI - Web framework
- psycopg2 - PostgreSQL driver
- pandas, numpy - Data processing
- aiohttp - Async HTTP

**Optional:**
- redis - Caching
- pytest - Testing
- uvicorn - ASGI server

See `requirements.txt` for full list.

---

## 🤝 Integration Examples

### JavaScript
```javascript
const response = await fetch('/api/volatility/0xa508cb...');
const data = await response.json();
console.log(`Vol: ${data.metrics.volatility_24h}`);
```

### Python
```python
import requests
resp = requests.get('/api/volatility/0xa508cb...')
vol = resp.json()['metrics']['volatility_24h']
```

### cURL
```bash
curl https://api.example.com/api/volatility/0xa508cb...
```

---

## 📝 Contest Info

**Contest:** Ninja API Forge - Injective  
**Duration:** Jan 28 - Feb 15, 2026  
**Category:** Developer API  

This project focuses on **API infrastructure** rather than consumer applications, emphasizing:
- ✓ Clean API design
- ✓ Developer experience
- ✓ Reliability & performance
- ✓ Documentation quality
- ✓ Practical utility

---

## 🤖 Continuous Integration

### GitHub Actions
```yaml
# Runs tests on push
- pytest test_api.py --cov
- Deploy to Railway if tests pass
```

### Health Monitoring
```bash
# Automated checks every 5 minutes
curl https://api.example.com/health
```

---

## 📚 Additional Resources

- **Injective Docs:** https://docs.injective.network
- **FastAPI Guide:** https://fastapi.tiangolo.com
- **PostgreSQL Tips:** https://www.postgresql.org/docs
- **API Design Best Practices:** https://restfulapi.net

---

## ⚡ Future Enhancements

Potential features beyond v1.0:
- WebSocket real-time updates
- Custom indicator computation
- Alert service with webhooks
- Advanced analytics (correlation, regime detection)
- Data export (CSV, Parquet)
- GraphQL endpoint
- API rate limiting tiers
- SDKs (Python, JavaScript, Go)

---

## 🐛 Known Issues & Limitations

- No API key authentication (add for production)
- Data history limited to 90 days
- Injective testnet data may be sparse
- No automatic market discovery (manual list)

---

## 📄 License

MIT License - See LICENSE file

---

## 🙏 Acknowledgments

- Built for **Ninja API Forge** contest
- Powered by **Injective Protocol**
- Stack: **FastAPI**, **PostgreSQL**, **Pandas**

---

## 💬 Support

### Questions?
1. Check [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
2. View interactive docs at `/api/docs`
3. Review examples in test_api.py
4. Check SETUP_GUIDE.md for common issues

### Found a Bug?
1. Run test suite: `pytest test_api.py -v`
2. Check database: `psql volatility_api volatility -c "SELECT COUNT(*) FROM volatility_metrics"`
3. View logs: Check console output or `api.log`

---

## 📞 Contact

- **GitHub:** (your repo)
- **Twitter:** (your handle)
- **Discord:** (your server)

---

**Built with ❤️ for Injective traders, devs, and builders**

Ready to use? Start with [SETUP_GUIDE.md](SETUP_GUIDE.md) →
