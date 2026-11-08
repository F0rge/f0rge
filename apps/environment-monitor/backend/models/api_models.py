from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class SensorInfo(BaseModel):
    manufacturer: str
    description: str
    interface: str
    address: str

class SensorData(BaseModel):
    temperature: float
    humidity: float
    last_update: str
    status: str
    sensor_info: SensorInfo

class HistoricalEntry(BaseModel):
    # No sensor_info here: it was a static ~150-byte object repeated on every
    # point (~40% of the range=all payload) and the frontend never reads it.
    # Sensor metadata lives on /api/sensor-data and the root endpoint.
    timestamp: str
    temperature: float
    humidity: float

class HealthResponse(BaseModel):
    status: str
    service: str
    checks: Optional[Dict[str, Any]] = None
    failures: Optional[List[str]] = None

class ApiInfo(BaseModel):
    message: str
    version: str
    sensor: SensorInfo
    endpoints: Dict[str, str]

class AverageMetrics(BaseModel):
    temperature_average: float
    temperature_min: float
    temperature_max: float
    temperature_std_dev: float
    humidity_average: float
    humidity_min: float
    humidity_max: float
    humidity_std_dev: float
    time_in_optimal_range: float
    temperature_trend: str
    humidity_trend: str
    timeframe: str
    data_points: int
