"""
app/services/weather_service.py

WeatherAPI.com integration service.

Responsibilities
----------------
- Fetch **current** weather conditions (irradiance proxy, temperature, humidity,
  wind speed, cloud cover) for a given lat/lon.
- Fetch a **forecast** horizon (up to 3 days) from WeatherAPI.com.
- Expose a ``WeatherData`` dataclass that the forecast pipeline consumes.
- Fall back gracefully to synthetic mock data when ``WEATHER_API_KEY`` is not
  configured, so local development works out of the box.

WeatherAPI.com free-tier endpoints used
----------------------------------------
  Current : GET /v1/current.json?key=...&q={lat},{lon}&aqi=no
  Forecast: GET /v1/forecast.json?key=...&q={lat},{lon}&days={days}&aqi=no

Irradiance estimation
---------------------
WeatherAPI does not expose a direct GHI field on its free tier.  We derive a
best-effort estimate from:
  GHI_est = max_solar_irradiance * (1 - cloud_cover / 100) * cos_correction
where ``cos_correction`` uses the current UV index as a daylight proxy.
For precise physics the forecast pipeline still passes this through pvlib or its
own physics layer -- the weather data just replaces the pvlib clear-sky baseline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# -- Constants ----------------------------------------------------------------

WEATHERAPI_BASE = "https://api.weatherapi.com/v1"
MAX_SOLAR_IRRADIANCE_W_M2 = 1000.0   # approximate peak clear-sky GHI
REQUEST_TIMEOUT_S = 10.0


# -- Data models --------------------------------------------------------------


@dataclass
class WeatherPoint:
    """A single weather observation or forecast hour."""

    timestamp: datetime
    temperature_c: float
    humidity_pct: float
    wind_speed_kph: float
    cloud_cover_pct: float
    uv_index: float
    condition_text: str
    is_day: bool = True
    # Derived -- populated by __post_init__
    irradiance_w_m2: float = 0.0

    def __post_init__(self) -> None:
        """Derive irradiance estimate if not supplied explicitly."""
        if self.irradiance_w_m2 == 0.0:
            self.irradiance_w_m2 = _estimate_irradiance(
                cloud_cover_pct=self.cloud_cover_pct,
                uv_index=self.uv_index,
                is_day=self.is_day,
            )


@dataclass
class WeatherData:
    """Full weather payload returned by the service."""

    latitude: float
    longitude: float
    location_name: str
    timezone_id: str
    current: WeatherPoint
    hourly_forecast: List[WeatherPoint] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    source: str = "weatherapi.com"   # "mock" when API key is absent


# -- Irradiance estimation helper ---------------------------------------------


def _estimate_irradiance(
    cloud_cover_pct: float,
    uv_index: float,
    is_day: bool,
) -> float:
    """
    Derive a rough GHI estimate from cloud cover and UV index.

    This is intentionally simple -- the physics layer in forecast_service will
    further refine the value using pvlib geometry if available.
    """
    if not is_day:
        return 0.0

    # UV index 0-11+; use as a proxy for solar elevation (capped at 1)
    uv_factor = min(uv_index / 8.0, 1.0)

    clear_sky_ghi = MAX_SOLAR_IRRADIANCE_W_M2 * uv_factor
    cloud_factor = 1.0 - (cloud_cover_pct / 100.0) * 0.75  # clouds reduce but not eliminate
    return max(0.0, clear_sky_ghi * cloud_factor)


# -- API client ---------------------------------------------------------------


class WeatherAPIClient:
    """Async HTTP client for WeatherAPI.com."""

    def __init__(self, api_key: str, base_url: str = WEATHERAPI_BASE) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def get_forecast(self, lat: float, lon: float, days: int = 1) -> dict:
        """Fetch current + hourly forecast (1-3 days)."""
        days = max(1, min(days, 3))  # free tier: max 3 days
        url = f"{self._base_url}/forecast.json"
        params = {
            "key": self._api_key,
            "q": f"{lat},{lon}",
            "days": days,
            "aqi": "no",
            "alerts": "no",
        }
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()


# -- Parsers ------------------------------------------------------------------


def _parse_current(raw: dict) -> WeatherPoint:
    """Parse the ``current`` block from WeatherAPI response."""
    cur = raw["current"]
    return WeatherPoint(
        timestamp=datetime.now(tz=timezone.utc),
        temperature_c=float(cur.get("temp_c", 25.0)),
        humidity_pct=float(cur.get("humidity", 50.0)),
        wind_speed_kph=float(cur.get("wind_kph", 0.0)),
        cloud_cover_pct=float(cur.get("cloud", 0.0)),
        uv_index=float(cur.get("uv", 4.0)),
        condition_text=cur.get("condition", {}).get("text", "Unknown"),
        is_day=bool(cur.get("is_day", 1)),
    )


def _parse_hourly_forecast(raw: dict) -> List[WeatherPoint]:
    """Parse hourly blocks from a WeatherAPI forecast response."""
    points: List[WeatherPoint] = []
    for day_block in raw.get("forecast", {}).get("forecastday", []):
        for hour in day_block.get("hour", []):
            try:
                ts = datetime.fromtimestamp(hour["time_epoch"], tz=timezone.utc)
                points.append(
                    WeatherPoint(
                        timestamp=ts,
                        temperature_c=float(hour.get("temp_c", 25.0)),
                        humidity_pct=float(hour.get("humidity", 50.0)),
                        wind_speed_kph=float(hour.get("wind_kph", 0.0)),
                        cloud_cover_pct=float(hour.get("cloud", 0.0)),
                        uv_index=float(hour.get("uv", 0.0)),
                        condition_text=hour.get("condition", {}).get("text", "Unknown"),
                        is_day=bool(hour.get("is_day", 1)),
                    )
                )
            except Exception as exc:
                logger.debug(f"Skipping malformed hourly entry: {exc}")
    return points


# -- Mock fallback ------------------------------------------------------------


def _mock_weather_data(lat: float, lon: float) -> WeatherData:
    """
    Return synthetic weather data for local development.

    Values are plausible daytime conditions for a mid-latitude solar plant.
    """
    now = datetime.now(tz=timezone.utc)
    hour = now.hour

    is_day = 6 <= hour <= 18
    uv = max(0.0, 6.0 * math.sin(math.pi * (hour - 6) / 12)) if is_day else 0.0
    cloud = 20.0

    current = WeatherPoint(
        timestamp=now,
        temperature_c=25.0 + 5.0 * math.sin(math.pi * (hour - 6) / 12),
        humidity_pct=55.0,
        wind_speed_kph=15.0,
        cloud_cover_pct=cloud,
        uv_index=uv,
        condition_text="Partly cloudy (mock)",
        is_day=is_day,
    )

    hourly: List[WeatherPoint] = []
    for delta_h in range(72):
        fh = (hour + delta_h) % 24
        fday = 6 <= fh <= 18
        fuv = max(0.0, 6.0 * math.sin(math.pi * (fh - 6) / 12)) if fday else 0.0
        hourly.append(
            WeatherPoint(
                timestamp=now + timedelta(hours=delta_h),
                temperature_c=25.0 + 5.0 * math.sin(math.pi * (fh - 6) / 12),
                humidity_pct=55.0,
                wind_speed_kph=15.0,
                cloud_cover_pct=cloud,
                uv_index=fuv,
                condition_text="Partly cloudy (mock)",
                is_day=fday,
            )
        )

    return WeatherData(
        latitude=lat,
        longitude=lon,
        location_name="Mock Location",
        timezone_id="UTC",
        current=current,
        hourly_forecast=hourly,
        source="mock",
    )


# -- Public service functions -------------------------------------------------


async def get_current_weather(lat: float, lon: float) -> WeatherData:
    """
    Fetch current weather for the given coordinates.

    Uses WeatherAPI.com when ``WEATHER_API_KEY`` is set; otherwise returns mock
    data so local development works without any external service.
    """
    if not settings.WEATHER_API_KEY:
        logger.debug("WEATHER_API_KEY not set -- using mock weather data.")
        return _mock_weather_data(lat, lon)

    try:
        client = WeatherAPIClient(api_key=settings.WEATHER_API_KEY)
        raw = await client.get_forecast(lat, lon, days=1)
        location = raw.get("location", {})
        current = _parse_current(raw)
        hourly = _parse_hourly_forecast(raw)
        return WeatherData(
            latitude=lat,
            longitude=lon,
            location_name=location.get("name", "Unknown"),
            timezone_id=location.get("tz_id", "UTC"),
            current=current,
            hourly_forecast=hourly,
            source="weatherapi.com",
        )
    except httpx.HTTPStatusError as exc:
        logger.error(
            f"WeatherAPI HTTP error {exc.response.status_code} for ({lat}, {lon}): "
            f"{exc.response.text[:200]}"
        )
        logger.warning("Falling back to mock weather data.")
        return _mock_weather_data(lat, lon)
    except Exception as exc:
        logger.error(f"WeatherAPI request failed for ({lat}, {lon}): {exc}")
        logger.warning("Falling back to mock weather data.")
        return _mock_weather_data(lat, lon)


async def get_forecast_weather(lat: float, lon: float, days: int = 3) -> WeatherData:
    """
    Fetch multi-day weather forecast for the given coordinates.

    Uses WeatherAPI.com when configured; otherwise returns mock data.
    ``days`` is capped at 3 (WeatherAPI.com free tier limit).
    """
    if not settings.WEATHER_API_KEY:
        logger.debug("WEATHER_API_KEY not set -- using mock forecast weather data.")
        return _mock_weather_data(lat, lon)

    try:
        client = WeatherAPIClient(api_key=settings.WEATHER_API_KEY)
        raw = await client.get_forecast(lat, lon, days=days)
        location = raw.get("location", {})
        current = _parse_current(raw)
        hourly = _parse_hourly_forecast(raw)
        return WeatherData(
            latitude=lat,
            longitude=lon,
            location_name=location.get("name", "Unknown"),
            timezone_id=location.get("tz_id", "UTC"),
            current=current,
            hourly_forecast=hourly,
            source="weatherapi.com",
        )
    except httpx.HTTPStatusError as exc:
        logger.error(
            f"WeatherAPI HTTP error {exc.response.status_code} for ({lat}, {lon}): "
            f"{exc.response.text[:200]}"
        )
        logger.warning("Falling back to mock weather data.")
        return _mock_weather_data(lat, lon)
    except Exception as exc:
        logger.error(f"WeatherAPI forecast request failed for ({lat}, {lon}): {exc}")
        logger.warning("Falling back to mock weather data.")
        return _mock_weather_data(lat, lon)
