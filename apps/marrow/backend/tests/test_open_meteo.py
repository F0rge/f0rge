"""Pure Open-Meteo aggregation — no HTTP, no database."""

from __future__ import annotations

from app.services.open_meteo import aggregate_hourly, weather_main_from_code


def test_weather_main_from_code_ranges() -> None:
    assert weather_main_from_code(0) == "Clear"
    assert weather_main_from_code(3) == "Clouds"
    assert weather_main_from_code(61) == "Rain"
    assert weather_main_from_code(71) == "Snow"
    assert weather_main_from_code(95) == "Thunderstorm"
    assert weather_main_from_code(None) is None
    assert weather_main_from_code(200) == "Clouds"


def test_aggregate_hourly_means_and_modal_code() -> None:
    day = aggregate_hourly(
        {
            "temperature_2m": [10.0, 12.0, None],
            "relative_humidity_2m": [50.0, 70.0],
            "surface_pressure": [1010.0, 1012.0],
            "weather_code": [3, 3, 61],
        }
    )
    assert day is not None
    assert day.temp_mean == 11.0
    assert day.temp_min == 10.0
    assert day.temp_max == 12.0
    assert day.humidity_mean == 60.0
    assert day.pressure_mean == 1011.0
    assert day.weather_main == "Clouds"


def test_aggregate_hourly_empty_temps_returns_none() -> None:
    assert aggregate_hourly({"temperature_2m": [None], "surface_pressure": [1013.0]}) is None
