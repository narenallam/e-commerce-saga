import sys
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Body
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

# Add parent directory to path to import common modules
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from common.database import Database
from common.logging import setup_logging
from common.config import get_settings
from common.monitoring import (
    setup_tracing,
    instrument_fastapi,
    RequestMetrics,
    start_metrics_server,
)

# Setup logging
logger = setup_logging("order-service")

# Get settings
settings = get_settings("order")

# Setup tracing (optional)
tracer = setup_tracing("order-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Order Service")
    await Database.connect("order")
    start_metrics_server(settings.order_service_port + 1000)
    yield
    logger.info("Shutting down Order Service")
    await Database.close()


app = FastAPI(title="Order Service", lifespan=lifespan)

# Add monitoring middleware
app.add_middleware(RequestMetrics)

# Instrument FastAPI (optional)
instrument_fastapi(app, "order-service")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.info("Health check requested")
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics():
    """Metrics endpoint"""
    return {"status": "metrics endpoint"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app", host="0.0.0.0", port=settings.order_service_port, reload=True
    )
