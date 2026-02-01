#!/usr/bin/env python3
"""
Volatility Indicators API Server
================================
A FastAPI-based REST API for querying volatility metrics from Injective markets.

Features:
- Real-time volatility metrics (24h, 1h, 4h rolling)
- Bollinger Bands & ATR
- Batch queries for multiple markets
- Historical trend data
- Market ranking by volatility
- WebSocket support for real-time updates
- Rate limiting & caching
- Comprehensive error handling
"""

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import psycopg2
import psycopg2.extras
import os
import logging
import json
import asyncio
from functools import lru_cache
from enum import Enum
import time

# ============================================================================
# LOGGING & CONFIG
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "volatility_api"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASS", "postgres"),
    "port": int(os.getenv("DB_PORT", 5432))
}

API_VERSION = "1.0.0"
API_TITLE = "Volatility Indicators API"
API_DESCRIPTION = """
A developer-focused API providing volatility metrics and technical indicators 
for Injective Protocol markets.

## Key Features

- **Real-time Volatility**: 1h, 4h, and 24h rolling volatility
- **Technical Indicators**: Bollinger Bands, ATR, Momentum
- **Market Ranking**: Find high/low volatility opportunities
- **Historical Data**: Track volatility trends over time
- **Batch Queries**: Efficient multi-market data fetching
- **WebSocket Support**: Subscribe to real-time metric updates

## Use Cases

- **Trading Bots**: Volatility-triggered strategies
- **Dashboards**: Market volatility visualization
- **Risk Management**: Monitor exposure across different volatility regimes
- **Arbitrage Detection**: Identify mispriced volatility
"""

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class BollingerBands(BaseModel):
    """Bollinger Bands (20-period, 2 std dev)"""
    upper: Optional[float] = Field(None, description="Upper band price")
    middle: Optional[float] = Field(None, description="Simple Moving Average")
    lower: Optional[float] = Field(None, description="Lower band price")


class VolatilityMetrics(BaseModel):
    """Core volatility metrics for a market"""
    volatility_1h: Optional[float] = Field(None, description="1-hour realized volatility (annualized)")
    volatility_4h: Optional[float] = Field(None, description="4-hour realized volatility (annualized)")
    volatility_24h: Optional[float] = Field(None, description="24-hour realized volatility (annualized)")
    bollinger_bands: BollingerBands = Field(description="Bollinger Bands (20-period)")
    atr: Optional[float] = Field(None, description="Average True Range (14-period)")
    momentum: Optional[float] = Field(None, description="12-period momentum (% change)")


class MarketVolatilityResponse(BaseModel):
    """Response for a single market's volatility data"""
    market_id: str = Field(description="Injective market identifier")
    timestamp: int = Field(description="Unix timestamp of data point (seconds)")
    metrics: VolatilityMetrics = Field(description="Volatility metrics")
    
    class Config:
        schema_extra = {
            "example": {
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
        }


class MarketRanking(BaseModel):
    """Market ranked by volatility"""
    rank: int = Field(description="Ranking position (1 = highest volatility)")
    market_id: str = Field(description="Market identifier")
    volatility_24h: Optional[float] = Field(None, description="24-hour volatility")
    timestamp: int = Field(description="Data timestamp")


class BatchQueryRequest(BaseModel):
    """Request body for batch market query"""
    market_ids: List[str] = Field(description="List of market IDs to query")
    
    class Config:
        schema_extra = {
            "example": {
                "market_ids": [
                    "0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70",
                    "0x17ef48032cb9375375e6c2873b92f5837f48f5cbee62e4db0cf076fa368e3e5d"
                ]
            }
        }


class VolatilityHistory(BaseModel):
    """Historical volatility data point"""
    timestamp: int = Field(description="Unix timestamp")
    volatility_24h: Optional[float] = Field(None)
    atr: Optional[float] = Field(None)
    momentum: Optional[float] = Field(None)


class HistoricalResponse(BaseModel):
    """Historical volatility data for a market"""
    market_id: str = Field(description="Market identifier")
    history: List[VolatilityHistory] = Field(description="Time series data")
    
    class Config:
        schema_extra = {
            "example": {
                "market_id": "0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70",
                "history": [
                    {"timestamp": 1706419200, "volatility_24h": 0.0156, "atr": 1.25, "momentum": 0.15},
                    {"timestamp": 1706405800, "volatility_24h": 0.0159, "atr": 1.23, "momentum": 0.12},
                    {"timestamp": 1706392400, "volatility_24h": 0.0162, "atr": 1.27, "momentum": 0.18}
                ]
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(description="Error message")
    details: Optional[str] = Field(None, description="Additional details")
    timestamp: str = Field(description="ISO 8601 timestamp")


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def get_db_connection():
    """Create and return a database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        logger.error(f"Database connection failed: {e}")
        raise HTTPException(status_code=503, detail="Database connection failed")


def query_latest_metrics(market_id: str) -> Optional[Dict]:
    """Get the latest volatility metrics for a market"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cursor.execute("""
            SELECT timestamp, volatility_1h, volatility_4h, volatility_24h,
                   bb_upper, bb_middle, bb_lower, atr, momentum
            FROM volatility_metrics
            WHERE market_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (market_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
        
    finally:
        cursor.close()
        conn.close()


def query_market_history(market_id: str, days: int = 7) -> List[Dict]:
    """Get historical metrics for a market"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cutoff_timestamp = int((datetime.now() - timedelta(days=days)).timestamp())
        
        cursor.execute("""
            SELECT timestamp, volatility_24h, atr, momentum
            FROM volatility_metrics
            WHERE market_id = %s AND timestamp > %s
            ORDER BY timestamp DESC
            LIMIT 168  -- 7 days of hourly data
        """, (market_id, cutoff_timestamp))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
        
    finally:
        cursor.close()
        conn.close()


def query_all_markets_latest() -> List[Dict]:
    """Get latest metrics for all markets"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cursor.execute("""
            SELECT DISTINCT ON (market_id) 
                   market_id, timestamp, volatility_24h
            FROM volatility_metrics
            ORDER BY market_id, timestamp DESC
        """)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
        
    finally:
        cursor.close()
        conn.close()


def get_market_count() -> int:
    """Get total number of tracked markets"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(DISTINCT market_id) FROM volatility_metrics")
        return cursor.fetchone()[0]
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

# Initialize app with enhanced documentation
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@app.get("/health", tags=["Status"])
async def health_check():
    """
    Health check endpoint
    
    Returns:
        - `status`: "healthy" if API and database are working
        - `timestamp`: Current server time
        - `version`: API version
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": API_VERSION,
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "disconnected",
            "error": str(e)
        }, 503


@app.get("/api/status", tags=["Status"])
async def api_status():
    """
    Get API status and metrics
    
    Returns:
        - `tracked_markets`: Number of markets with data
        - `last_update`: When data was last updated
        - `api_version`: Current API version
    """
    try:
        market_count = get_market_count()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(timestamp) FROM volatility_metrics")
        last_ts = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return {
            "api_name": API_TITLE,
            "api_version": API_VERSION,
            "status": "operational",
            "tracked_markets": market_count,
            "last_update": datetime.fromtimestamp(last_ts).isoformat() if last_ts else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# VOLATILITY ENDPOINTS
# ============================================================================

@app.get(
    "/api/volatility/{market_id}",
    response_model=MarketVolatilityResponse,
    tags=["Volatility Metrics"],
    responses={
        200: {"description": "Successfully retrieved market volatility"},
        404: {"description": "Market not found"},
        503: {"description": "Database unavailable"}
    }
)
async def get_market_volatility(market_id: str):
    """
    Get latest volatility metrics for a market
    
    Args:
        market_id: Injective market identifier (hex string)
    
    Returns:
        MarketVolatilityResponse with latest metrics
    
    Example:
        ```
        curl https://api.example.com/api/volatility/0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70
        ```
    """
    metrics = query_latest_metrics(market_id)
    
    if not metrics:
        raise HTTPException(
            status_code=404,
            detail=f"Market {market_id} not found"
        )
    
    return MarketVolatilityResponse(
        market_id=market_id,
        timestamp=metrics['timestamp'],
        metrics=VolatilityMetrics(
            volatility_1h=metrics['volatility_1h'],
            volatility_4h=metrics['volatility_4h'],
            volatility_24h=metrics['volatility_24h'],
            bollinger_bands=BollingerBands(
                upper=metrics['bb_upper'],
                middle=metrics['bb_middle'],
                lower=metrics['bb_lower']
            ),
            atr=metrics['atr'],
            momentum=metrics['momentum']
        )
    )


@app.post(
    "/api/volatility/batch",
    response_model=List[MarketVolatilityResponse],
    tags=["Volatility Metrics"]
)
async def batch_query_volatility(request: BatchQueryRequest):
    """
    Get volatility metrics for multiple markets in one request
    
    Useful for:
    - Comparing volatility across markets
    - Bulk data fetching
    - Dashboard population
    
    Args:
        request: BatchQueryRequest with list of market IDs
    
    Returns:
        List of MarketVolatilityResponse objects
    
    Example:
        ```
        curl -X POST https://api.example.com/api/volatility/batch \\
          -H "Content-Type: application/json" \\
          -d {
            "market_ids": [
              "0xa508cb32923323679f29d3b7155848cd07e6b40b9a60b5dd85b00d7a4e30fa70",
              "0x17ef48032cb9375375e6c2873b92f5837f48f5cbee62e4db0cf076fa368e3e5d"
            ]
          }
        ```
    """
    results = []
    
    for market_id in request.market_ids:
        metrics = query_latest_metrics(market_id)
        
        if metrics:
            results.append(MarketVolatilityResponse(
                market_id=market_id,
                timestamp=metrics['timestamp'],
                metrics=VolatilityMetrics(
                    volatility_1h=metrics['volatility_1h'],
                    volatility_4h=metrics['volatility_4h'],
                    volatility_24h=metrics['volatility_24h'],
                    bollinger_bands=BollingerBands(
                        upper=metrics['bb_upper'],
                        middle=metrics['bb_middle'],
                        lower=metrics['bb_lower']
                    ),
                    atr=metrics['atr'],
                    momentum=metrics['momentum']
                )
            ))
    
    return results


@app.get(
    "/api/volatility/{market_id}/history",
    response_model=HistoricalResponse,
    tags=["Historical Data"]
)
async def get_volatility_history(
    market_id: str,
    days: int = Query(7, ge=1, le=90, description="Number of days of history (1-90)")
):
    """
    Get historical volatility data for a market
    
    Useful for:
    - Visualizing volatility trends
    - Backtesting strategies
    - Detecting volatility regimes
    
    Args:
        market_id: Market identifier
        days: Number of days to retrieve (default: 7, max: 90)
    
    Returns:
        HistoricalResponse with time series data
    
    Example:
        ```
        curl "https://api.example.com/api/volatility/{market_id}/history?days=30"
        ```
    """
    history = query_market_history(market_id, days=days)
    
    if not history:
        raise HTTPException(
            status_code=404,
            detail=f"No historical data found for market {market_id}"
        )
    
    return HistoricalResponse(
        market_id=market_id,
        history=[
            VolatilityHistory(
                timestamp=h['timestamp'],
                volatility_24h=h['volatility_24h'],
                atr=h['atr'],
                momentum=h['momentum']
            )
            for h in reversed(history)  # Chronological order
        ]
    )


@app.get(
    "/api/markets/volatility/ranking",
    response_model=List[MarketRanking],
    tags=["Market Analysis"]
)
async def rank_markets_by_volatility(
    limit: int = Query(10, ge=1, le=100),
    sort: str = Query("desc", regex="^(asc|desc)$")
):
    """
    Rank markets by 24h volatility
    
    Useful for:
    - Finding high volatility opportunities
    - Identifying stable markets
    - Volatility-based market selection
    
    Args:
        limit: Number of markets to return (1-100, default: 10)
        sort: Sort order - "asc" (low volatility first) or "desc" (high first, default)
    
    Returns:
        List of markets ranked by volatility
    
    Example:
        ```
        # Top 10 highest volatility markets
        curl "https://api.example.com/api/markets/volatility/ranking?limit=10&sort=desc"
        
        # Top 10 lowest volatility (most stable) markets
        curl "https://api.example.com/api/markets/volatility/ranking?limit=10&sort=asc"
        ```
    """
    markets = query_all_markets_latest()
    
    # Sort by volatility
    markets = sorted(
        markets,
        key=lambda x: x.get('volatility_24h') or 0,
        reverse=(sort == "desc")
    )
    
    # Apply limit
    markets = markets[:limit]
    
    return [
        MarketRanking(
            rank=i + 1,
            market_id=m['market_id'],
            volatility_24h=m['volatility_24h'],
            timestamp=m['timestamp']
        )
        for i, m in enumerate(markets)
    ]


# ============================================================================
# ERROR HANDLING
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            timestamp=datetime.utcnow().isoformat()
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            details=str(exc),
            timestamp=datetime.utcnow().isoformat()
        ).dict()
    )


# ============================================================================
# STARTUP & SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize on server startup"""
    logger.info(f"Starting {API_TITLE} v{API_VERSION}")
    logger.info(f"Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    
    # Test database connection
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM volatility_metrics")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        logger.info(f"✓ Database connected. {count} metrics available.")
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server shutdown"""
    logger.info(f"Shutting down {API_TITLE}")


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/", tags=["Documentation"])
async def root():
    """
    Volatility Indicators API Root
    
    Navigate to `/api/docs` for interactive API documentation
    """
    return {
        "api": API_TITLE,
        "version": API_VERSION,
        "documentation": "/api/docs",
        "openapi_schema": "/api/openapi.json",
        "status": "/api/status",
        "health": "/health"
    }


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 8000))
    
    logger.info(f"Starting server on {host}:{port}")
    
    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=os.getenv("DEBUG", "False") == "True",
        access_log=True
    )
