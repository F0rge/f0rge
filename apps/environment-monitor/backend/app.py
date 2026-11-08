from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from datetime import datetime, timezone
from typing import List
import uvicorn
import logging

from models import SensorData, HistoricalEntry, HealthResponse, ApiInfo, AverageMetrics
from services import SensorService
from utils import calculate_comprehensive_metrics, calculate_metrics_from_aggregate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sensor_service = SensorService()


@asynccontextmanager
async def lifespan(app):
    yield
    try:
        with sensor_service._conn_lock:
            # Refresh planner stats if the query mix warrants it (cheap no-op
            # otherwise) — the recommended place to run this is on close.
            sensor_service.conn.execute("PRAGMA optimize")
            sensor_service.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            sensor_service.conn.close()
        logger.info("SQLite connection checkpointed and closed")
    except Exception as e:
        logger.error(f"error during DB shutdown: {e}")


# Initialize FastAPI app
app = FastAPI(
    title="ENVIRONMENT_MONITOR Sensor API",
    description="API for ENVIRONMENT_MONITOR temperature and humidity sensor data",
    version="1.7.0",
    lifespan=lifespan,
)

# ===== Core API Endpoints =====

@app.get("/", response_model=ApiInfo)
async def root():
    """Root endpoint with API information"""
    return {
        "message": "ENVIRONMENT_MONITOR Sensor Backend API",
        "version": "1.7.0",
        "sensor": sensor_service.get_sensor_info(),
        "endpoints": {
            "sensor_data": "/api/sensor-data",
            "historical_data": "/api/historical-data",
            "average_metrics": "/api/average-metrics",
            "download_data": "/api/download-data",
            "health": "/health"
        }
    }

@app.get("/api/sensor-data", response_model=SensorData, tags=["Sensor"])
async def get_sensor_data():
    """Get current temperature and humidity sensor readings"""
    return sensor_service.get_current_data()

@app.get("/api/live-reading", tags=["Sensor"])
async def get_live_reading():
    """Current raw sensor reading at full precision — not persisted, streamed live."""
    return sensor_service.get_live_reading()

@app.get("/api/historical-data", response_model=List[HistoricalEntry], tags=["Sensor"])
async def get_historical_data(
    range: str = Query(
        default='6h',
        description="Time range: 5m, 1h, 6h, 1d, 1w, ytd, all",
    )
):
    """Get historical sensor data for specified time range.

    Filtering and downsampling are performed in SQL by SensorService.
    """
    try:
        return await run_in_threadpool(sensor_service.get_historical_data, range)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/average-metrics", response_model=AverageMetrics, tags=["Analytics"])
async def get_average_metrics(
    range: str = Query(
        default='6h',
        description="Time range: 5m, 1h, 6h, 1d, 1w, ytd, all",
    )
):
    """Get comprehensive metrics including averages, std dev, optimal range time, and trends.

    Stats are aggregated in SQL over the full window (exact min/max/avg/std/optimal%);
    trend direction uses the downsampled series since it only compares first vs last.
    """
    try:
        agg = await run_in_threadpool(sensor_service.get_aggregate_metrics, range)
        if agg is None:
            return calculate_comprehensive_metrics([], range)
        trend_data = await run_in_threadpool(sensor_service.get_historical_data, range)
        return calculate_metrics_from_aggregate(agg, trend_data, range)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/download-data", tags=["Export"])
async def download_data():
    """Download all historical data as CSV file.

    Full resolution: streams every raw row from SQLite in chunks. Must NOT go
    through get_historical_data('all'), which returns the downsampled chart
    rollup. Starlette iterates the sync generator in a threadpool, so the
    event loop is never blocked.
    """
    filename = f"environment_monitor_sensor_data_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        sensor_service.iter_csv_rows(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint for monitoring service status.

    Returns 200 with details when sensor is fresh + DB responds; 503 otherwise.
    """
    checks: dict = {}
    failures: list[str] = []

    current = sensor_service.get_current_data()
    sensor_status = current.get("status", "")
    last_update = current.get("last_update", "")

    # Sensor freshness: last reading must be < 60s old.
    age_seconds: float | None = None
    if last_update:
        try:
            ts = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
            age_seconds = (datetime.now(timezone.utc) - ts).total_seconds()
        except ValueError:
            age_seconds = None
    if age_seconds is None:
        failures.append("no sensor reading available")
    elif age_seconds >= 60:
        failures.append(f"sensor reading stale ({age_seconds:.1f}s old)")
    checks["sensor_age_seconds"] = round(age_seconds, 1) if age_seconds is not None else None

    # Sensor status: must not be an error state.
    if sensor_status.startswith("error") or sensor_status == "sensor not available":
        failures.append(f"sensor status: {sensor_status}")
    checks["sensor_status"] = sensor_status

    # DB liveness: simple SELECT 1.
    try:
        with sensor_service._conn_lock:
            sensor_service.conn.execute("SELECT 1").fetchone()
        checks["db"] = "ok"
    except Exception as e:
        failures.append(f"db error: {e}")
        checks["db"] = "error"

    if failures:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "environment_monitor-backend",
                "failures": failures,
                "checks": checks,
            },
        )

    return {
        "status": "healthy",
        "service": "environment_monitor-backend",
        "checks": checks,
    }

# ===== Main Entry Point =====

if __name__ == "__main__":
    logger.info("Starting Environment Monitor API...")
    logger.info("Available endpoints:")
    logger.info("   - API Documentation: http://0.0.0.0:5001/docs")
    logger.info("   - Sensor Data: http://0.0.0.0:5001/api/sensor-data")
    logger.info("   - Comprehensive Metrics: http://0.0.0.0:5001/api/average-metrics")

    uvicorn.run(app, host="0.0.0.0", port=5001)
