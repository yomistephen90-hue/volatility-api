# Volatility Indicators API - Documentation

## Overview

**Volatility Indicators API** is a production-grade REST API that provides real-time volatility metrics and technical indicators for Injective Protocol markets. Built for developers to integrate volatility-based trading strategies, risk monitoring, and market analysis.

**API Base URL:** `https://volatility-api.example.com` (adjust for your deployment)

**API Version:** 1.0.0

---

## Quick Start

### 1. Get Latest Volatility for a Market

```bash
curl https://volatility-api.example.com/api/volatility/0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70
```

**Response:**
```json
{
  "market_id": "0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70",
  "timestamp": 1706419200,
  "metrics": {
    "volatility_1h": 0.0234,
    "volatility_4h": 0.0189,
    "volatility_24h": 0.0156,
    "bollinger_bands": {
      "upper": 52.40,
      "middle": 50.20,
      "lower": 48.00
    },
    "atr": 1.25,
    "momentum": 0.15
  }
}
```

### 2. Compare Multiple Markets

```bash
curl -X POST https://volatility-api.example.com/api/volatility/batch \
  -H "Content-Type: application/json" \
  -d '{
    "market_ids": [
      "0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70",
      "0x17ef48032cb9375375e6c2873b92f5837f48f5cbee62e4db0cf076fa368e3e5d"
    ]
  }'
```

### 3. Find High-Volatility Markets

```bash
curl "https://volatility-api.example.com/api/markets/volatility/ranking?limit=10&sort=desc"
```

---

## Endpoints

### Status & Health

#### `GET /health`

Health check endpoint. Returns API and database status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-29T10:15:23.456Z",
  "version": "1.0.0",
  "database": "connected"
}
```

#### `GET /api/status`

Get detailed API status and metrics.

**Response:**
```json
{
  "api_name": "Volatility Indicators API",
  "api_version": "1.0.0",
  "status": "operational",
  "tracked_markets": 42,
  "last_update": "2026-01-29T10:15:00Z",
  "timestamp": "2026-01-29T10:15:23Z"
}
```

---

### Volatility Metrics

#### `GET /api/volatility/{market_id}`

Get latest volatility metrics for a specific market.

**Parameters:**
- `market_id` (path, required): Injective market identifier (hex string)

**Response:** `MarketVolatilityResponse`
```json
{
  "market_id": "0xa508cb...",
  "timestamp": 1706419200,
  "metrics": {
    "volatility_1h": 0.0234,
    "volatility_4h": 0.0189,
    "volatility_24h": 0.0156,
    "bollinger_bands": {
      "upper": 52.40,
      "middle": 50.20,
      "lower": 48.00
    },
    "atr": 1.25,
    "momentum": 0.15
  }
}
```

**Use Cases:**
- Build a single-market dashboard
- Monitor volatility for a specific trading pair
- Check if market is suitable for options trading
- Detect volatility regime changes

**Example:**
```bash
# Get INJ/USDT volatility
curl https://volatility-api.example.com/api/volatility/0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70
```

---

#### `POST /api/volatility/batch`

Get volatility metrics for multiple markets at once. More efficient than multiple individual requests.

**Request Body:**
```json
{
  "market_ids": [
    "0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70",
    "0x17ef48032cb9375375e6c2873b92f5837f48f5cbee62e4db0cf076fa368e3e5d",
    "0xca51c18b48c2d7fda3e6b5a40491876ca06c39f6984152e44fcb4c4a3e4f25e5"
  ]
}
```

**Response:** Array of `MarketVolatilityResponse` objects

**Use Cases:**
- Dashboard showing multiple markets
- Portfolio volatility analysis
- Bulk data export
- Comparing volatility across pairs

**Example with cURL:**
```bash
curl -X POST https://volatility-api.example.com/api/volatility/batch \
  -H "Content-Type: application/json" \
  -d '{
    "market_ids": [
      "0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70",
      "0x17ef48032cb9375375e6c2873b92f5837f48f5cbee62e4db0cf076fa368e3e5d"
    ]
  }'
```

**Example with JavaScript:**
```javascript
const markets = [
  "0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70",
  "0x17ef48032cb9375375e6c2873b92f5837f48f5cbee62e4db0cf076fa368e3e5d"
];

const response = await fetch('https://volatility-api.example.com/api/volatility/batch', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ market_ids: markets })
});

const data = await response.json();
console.log(data);
```

**Example with Python:**
```python
import requests

markets = [
    "0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70",
    "0x17ef48032cb9375375e6c2873b92f5837f48f5cbee62e4db0cf076fa368e3e5d"
]

response = requests.post(
    'https://volatility-api.example.com/api/volatility/batch',
    json={'market_ids': markets}
)

data = response.json()
for market in data:
    print(f"{market['market_id']}: {market['metrics']['volatility_24h']}")
```

---

### Historical Data

#### `GET /api/volatility/{market_id}/history`

Get historical volatility data for trend analysis and backtesting.

**Parameters:**
- `market_id` (path, required): Market identifier
- `days` (query, optional): Number of days of history to return (1-90, default: 7)

**Response:** `HistoricalResponse`
```json
{
  "market_id": "0xa508cb...",
  "history": [
    {
      "timestamp": 1706419200,
      "volatility_24h": 0.0156,
      "atr": 1.25,
      "momentum": 0.15
    },
    {
      "timestamp": 1706405800,
      "volatility_24h": 0.0159,
      "atr": 1.23,
      "momentum": 0.12
    },
    {
      "timestamp": 1706392400,
      "volatility_24h": 0.0162,
      "atr": 1.27,
      "momentum": 0.18
    }
  ]
}
```

**Use Cases:**
- Volatility trend analysis
- Mean reversion strategies
- Historical volatility comparison
- Volatility regime detection

**Examples:**
```bash
# Get last 7 days of volatility (default)
curl https://volatility-api.example.com/api/volatility/0xa508cb.../history

# Get last 30 days
curl "https://volatility-api.example.com/api/volatility/0xa508cb.../history?days=30"

# Get last 90 days (maximum)
curl "https://volatility-api.example.com/api/volatility/0xa508cb.../history?days=90"
```

---

### Market Analysis

#### `GET /api/markets/volatility/ranking`

Rank all tracked markets by volatility. Find opportunities and stable markets.

**Parameters:**
- `limit` (query, optional): Number of markets to return (1-100, default: 10)
- `sort` (query, optional): Sort order - "asc" (low vol first) or "desc" (high vol first, default)

**Response:** Array of `MarketRanking` objects
```json
[
  {
    "rank": 1,
    "market_id": "0x17ef48032cb9375375e6c2873b92f5837f48f5cbee62e4db0cf076fa368e3e5d",
    "volatility_24h": 0.0234,
    "timestamp": 1706419200
  },
  {
    "rank": 2,
    "market_id": "0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70",
    "volatility_24h": 0.0189,
    "timestamp": 1706419200
  },
  {
    "rank": 3,
    "market_id": "0xca51c18b48c2d7fda3e6b5a40491876ca06c39f6984152e44fcb4c4a3e4f25e5",
    "volatility_24h": 0.0156,
    "timestamp": 1706419200
  }
]
```

**Use Cases:**
- Finding high-volatility trading opportunities
- Identifying stable, liquid markets for hedging
- Portfolio volatility diversification
- Market screening for strategies

**Examples:**
```bash
# Top 10 highest volatility markets
curl "https://volatility-api.example.com/api/markets/volatility/ranking?limit=10&sort=desc"

# Top 20 lowest volatility (most stable) markets
curl "https://volatility-api.example.com/api/markets/volatility/ranking?limit=20&sort=asc"

# Top 5 markets
curl "https://volatility-api.example.com/api/markets/volatility/ranking?limit=5"
```

---

## Response Format

All successful responses return HTTP 200 with JSON body.

All error responses include:
```json
{
  "error": "Error message description",
  "details": "Additional context if available",
  "timestamp": "2026-01-29T10:15:23Z"
}
```

---

## Metrics Explained

### Volatility (1h, 4h, 24h)

**Definition:** Annualized standard deviation of log returns over the specified period.

**Interpretation:**
- **0.01 (1%):** Very low volatility (stable)
- **0.03 (3%):** Low volatility
- **0.05 (5%):** Moderate volatility
- **0.10 (10%):** High volatility (good for traders)
- **0.20+ (20%+):** Extreme volatility (risky)

**Use Case:** Select trading strategies based on volatility level
- Low vol: Use slower-moving strategies, wider stops
- High vol: Use tight stops, fast-moving strategies

---

### Bollinger Bands

**Definition:** Price bands at ±2 standard deviations from 20-period SMA.

**Components:**
- **Upper Band:** Price + (2 × StdDev)
- **Middle Band:** 20-period Simple Moving Average
- **Lower Band:** Price - (2 × StdDev)

**Interpretation:**
- Price near upper band = overbought
- Price near lower band = oversold
- Wide bands = high volatility
- Narrow bands = low volatility (potential breakout)

---

### ATR (Average True Range)

**Definition:** 14-period average of true range (largest of: high-low, |high-close|, |low-close|).

**Interpretation:**
- Measures price volatility in absolute terms
- Higher ATR = larger average price moves
- Lower ATR = tighter price range
- Useful for setting stop losses and position sizing

**Use Case:** Position sizing
- If ATR = 2.5, risk 1 ATR per trade = 2.5 unit stop loss

---

### Momentum

**Definition:** 12-period rate of change: (Current Price - Price 12 periods ago) / Price 12 periods ago

**Range:** -1 to +1 (or -100% to +100%)

**Interpretation:**
- Positive = price rising (bullish)
- Negative = price falling (bearish)
- > 0.05 (5%) = strong uptrend
- < -0.05 (-5%) = strong downtrend

---

## Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 200 | Success | - |
| 400 | Bad request | Check request format and parameters |
| 404 | Not found | Market ID may not exist or have data yet |
| 429 | Rate limited | Wait before retrying (if applicable) |
| 500 | Server error | Try again, contact support if persistent |
| 503 | Service unavailable | Database offline, try again soon |

---

## Client Examples

### JavaScript

```javascript
// Fetch single market
async function getVolatility(marketId) {
  const response = await fetch(
    `https://volatility-api.example.com/api/volatility/${marketId}`
  );
  const data = await response.json();
  return data;
}

// Get multiple markets
async function getMultipleMarkets(marketIds) {
  const response = await fetch(
    'https://volatility-api.example.com/api/volatility/batch',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ market_ids: marketIds })
    }
  );
  return await response.json();
}

// Find high volatility opportunities
async function findHighVolatilityMarkets() {
  const response = await fetch(
    'https://volatility-api.example.com/api/markets/volatility/ranking?limit=20&sort=desc'
  );
  return await response.json();
}

// Usage
const inj_usdt = "0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70";
getVolatility(inj_usdt).then(data => {
  console.log(`INJ/USDT 24h volatility: ${(data.metrics.volatility_24h * 100).toFixed(2)}%`);
});
```

### Python

```python
import requests
from datetime import datetime

BASE_URL = "https://volatility-api.example.com"

def get_volatility(market_id):
    """Get latest volatility for a market"""
    response = requests.get(f"{BASE_URL}/api/volatility/{market_id}")
    return response.json()

def get_batch_volatility(market_ids):
    """Get volatility for multiple markets"""
    response = requests.post(
        f"{BASE_URL}/api/volatility/batch",
        json={"market_ids": market_ids}
    )
    return response.json()

def get_history(market_id, days=7):
    """Get historical volatility"""
    response = requests.get(
        f"{BASE_URL}/api/volatility/{market_id}/history",
        params={"days": days}
    )
    return response.json()

def rank_markets(limit=10, sort="desc"):
    """Get markets ranked by volatility"""
    response = requests.get(
        f"{BASE_URL}/api/markets/volatility/ranking",
        params={"limit": limit, "sort": sort}
    )
    return response.json()

# Usage example
if __name__ == "__main__":
    # Get volatility for INJ/USDT
    inj_market = "0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70"
    data = get_volatility(inj_market)
    
    vol_24h = data['metrics']['volatility_24h']
    print(f"INJ/USDT 24h Volatility: {vol_24h:.4f} ({vol_24h*100:.2f}%)")
    
    # Find high volatility opportunities
    high_vol_markets = rank_markets(limit=10, sort="desc")
    print("\nTop 10 Highest Volatility Markets:")
    for market in high_vol_markets:
        print(f"  #{market['rank']}: {market['volatility_24h']:.4f}")
```

---

## Rate Limiting

**Current limits (adjustable based on load):**
- Public endpoints: 100 requests/minute per IP
- Batch queries: Count as 1 request regardless of market count

If rate limited, you'll receive a 429 response. Retry after the delay indicated in response headers.

---

## API Best Practices

1. **Batch queries when possible** - More efficient than multiple individual requests
2. **Cache data locally** - Don't query the same market every second
3. **Handle errors gracefully** - Implement retry logic with exponential backoff
4. **Use appropriate timeframes** - Don't over-query for real-time systems
5. **Monitor API status** - Check `/api/status` endpoint periodically

---

## Changelog

### v1.0.0 (Jan 2026)
- Initial release
- Core volatility metrics endpoints
- Market ranking by volatility
- Historical data support
- Batch query capability

---

## Support & Documentation

- **Interactive Docs:** `/api/docs` (Swagger UI)
- **OpenAPI Schema:** `/api/openapi.json`
- **GitHub:** (your repo)
- **Issues:** (your issue tracker)

---

## License

This API is provided as-is. See LICENSE file for details.
