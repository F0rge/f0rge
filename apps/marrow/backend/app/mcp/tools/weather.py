from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import Context, FastMCP

from app.mcp.observability import instrument_tool
from app.mcp.tools._common import _mcp_user_id, _validate_date
from app.services.weather import WeatherService


def register_weather_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("get_weather_for_entry")
    async def get_weather_for_entry(date: str, ctx: Context = None) -> Optional[dict[str, Any]]:
        """Return the daily weather snapshot for an entry date (YYYY-MM-DD).

        Returns null when no readings exist for that date. Daily Open-Meteo
        snapshot (pressure, temperature, humidity). Use get_entry
        for symptom scores on the same day; list_health_metrics for wearable data.
        """
        parsed = _validate_date(date, "date")
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            summary = await WeatherService(db).get_daily_summary(parsed)

        if summary is None:
            return None

        return {
            "date": str(summary.date),
            "pressure_mean": summary.pressure_mean,
            "pressure_min": summary.pressure_min,
            "pressure_max": summary.pressure_max,
            "pressure_delta_24h": summary.pressure_delta_24h,
            "temp_mean": summary.temp_mean,
            "temp_min": summary.temp_min,
            "temp_max": summary.temp_max,
            "humidity_mean": summary.humidity_mean,
            "reading_count": summary.reading_count,
        }
