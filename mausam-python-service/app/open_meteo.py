"""
Thin client for Open-Meteo's free APIs (no API key required):
  - Geocoding:    https://geocoding-api.open-meteo.com/v1/search
  - Forecast:     https://api.open-meteo.com/v1/forecast
  - Air quality:  https://air-quality-api.open-meteo.com/v1/air-quality
  - Marine:       https://marine-api.open-meteo.com/v1/marine (coastal only)

All functions raise OpenMeteoError on failure so the caller can decide
whether to fall back to mock data.
"""

import time
import threading

import requests

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"

TIMEOUT_SECONDS = 4
RETRY_DELAY_SECONDS = 0.3

# In-memory cache so repeated requests for the same city during a session
# don't re-hit the geocoder every time.
_geocode_cache: dict = {}

# Shared in-memory cache for all requests handled by this Python process.
# A location can be requested by several persona endpoints at nearly the same
# time. The per-key locks below prevent a "cache stampede": only ONE request
# for a given location/data type is allowed to reach Open-Meteo while the
# others wait for that result.
_fetch_cache: dict = {}
_fetch_locks: dict = {}
_cache_guard = threading.Lock()

# Keep successful forecast/air-quality/marine responses for one hour. Weather
# model data does not need to be fetched again for every persona card.
CACHE_TTL_SECONDS = 3600

# If Open-Meteo rate-limits a request, briefly remember that failure so
# concurrent/repeated frontend calls do not immediately create another
# request storm. This does NOT create weather data or act as a fallback.
_RATE_LIMIT_COOLDOWN_SECONDS = 30
_rate_limit_cache: dict = {}


def _get_cache_lock(cache_key):
    with _cache_guard:
        return _fetch_locks.setdefault(cache_key, threading.Lock())


def _cached_fetch(cache_key, fetch_fn):
    """Return cached data and coalesce simultaneous requests for one key."""
    now = time.time()

    entry = _fetch_cache.get(cache_key)
    if entry is not None and entry[0] > now:
        return entry[1]

    rate_limited_until = _rate_limit_cache.get(cache_key, 0)
    if rate_limited_until > now:
        raise OpenMeteoError(
            "Open-Meteo is temporarily rate limiting this location. "
            "Please wait a moment and try again."
        )

    lock = _get_cache_lock(cache_key)

    # Only one thread performs the upstream request. Everyone else waits and
    # then re-checks the cache.
    with lock:
        now = time.time()

        entry = _fetch_cache.get(cache_key)
        if entry is not None and entry[0] > now:
            return entry[1]

        rate_limited_until = _rate_limit_cache.get(cache_key, 0)
        if rate_limited_until > now:
            raise OpenMeteoError(
                "Open-Meteo is temporarily rate limiting this location. "
                "Please wait a moment and try again."
            )

        try:
            result = fetch_fn()
        except OpenMeteoError as exc:
            if "HTTP 429" in str(exc):
                _rate_limit_cache[cache_key] = time.time() + _RATE_LIMIT_COOLDOWN_SECONDS
            raise

        _fetch_cache[cache_key] = (time.time() + CACHE_TTL_SECONDS, result)
        _rate_limit_cache.pop(cache_key, None)
        return result


class OpenMeteoError(Exception):
    pass


def _get_json(url: str, params: dict, what: str) -> dict:
    """GET JSON. Do not repeatedly retry rate-limited requests."""

    try:
        resp = requests.get(
            url,
            params=params,
            timeout=TIMEOUT_SECONDS
        )

        if resp.status_code == 429:
            raise OpenMeteoError(
                f"{what} was rate limited by Open-Meteo (HTTP 429). "
                "Please wait a moment and try again."
            )

        if resp.status_code == 403:
            raise OpenMeteoError(
                f"{what} was rejected by Open-Meteo (HTTP 403 Forbidden). "
                "The upstream service has temporarily denied this request. "
                "Please wait and try again."
            )

        resp.raise_for_status()
        return resp.json()

    except OpenMeteoError:
        raise

    except requests.RequestException as exc:
        raise OpenMeteoError(
            f"{what} failed: {exc}"
        ) from exc

# WMO weather codes -> human-readable condition (per Open-Meteo's table)
_WEATHER_CODE_MAP = {
    0: "Clear",
    1: "Mainly Clear",
    2: "Partly Cloudy",
    3: "Cloudy",
    45: "Foggy",
    48: "Foggy",
    51: "Light Drizzle",
    53: "Drizzle",
    55: "Heavy Drizzle",
    61: "Light Rain",
    63: "Rain",
    65: "Heavy Rain",
    71: "Light Snow",
    73: "Snow",
    75: "Heavy Snow",
    80: "Rain Showers",
    81: "Rain Showers",
    82: "Violent Rain Showers",
    95: "Thunderstorms",
    96: "Thunderstorms",
    99: "Thunderstorms",
}


def weather_code_to_condition(code) -> str:
    try:
        return _WEATHER_CODE_MAP.get(int(code), "Cloudy")
    except (TypeError, ValueError):
        return "Cloudy"


def geocode_city(city: str) -> dict:
    """Resolve a city name to coordinates + timezone. Cached per city name."""
    key = city.strip().lower()
    if key in _geocode_cache:
        return _geocode_cache[key]

    data = _get_json(
        GEOCODE_URL,
        {"name": city, "count": 1, "language": "en", "format": "json"},
        f"Geocoding request for '{city}'",
    )

    results = data.get("results")
    if not results:
        raise OpenMeteoError(f"No location found for '{city}'")

    top = results[0]
    resolved = {
        "name": top.get("name", city),
        "country": top.get("country", ""),
        "latitude": top["latitude"],
        "longitude": top["longitude"],
        "timezone": top.get("timezone", "auto"),
    }
    _geocode_cache[key] = resolved
    return resolved


def search_locations(query: str, count: int = 8) -> list:
    """Search Open-Meteo's global gazetteer — covers cities, towns, and
    villages worldwide, not just a curated list. Returns [] on no match
    or if the query is too short; raises OpenMeteoError only on a real
    network/API failure (after retrying once) so callers can fall back
    sensibly."""
    query = (query or "").strip()
    if len(query) < 2:
        return []

    data = _get_json(
        GEOCODE_URL,
        {"name": query, "count": count, "language": "en", "format": "json"},
        f"Location search for '{query}'",
    )

    results = []
    for r in data.get("results", []):
        region_parts = [p for p in [r.get("admin1"), r.get("country")] if p]
        results.append({
            "city": r.get("name", query),
            "region": ", ".join(region_parts) if region_parts else "",
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
        })
    return results


def fetch_forecast(lat: float, lon: float, timezone: str) -> dict:
    cache_key = ("forecast", round(lat, 3), round(lon, 3))

    def do_fetch():
        params = {
            "latitude": lat,
            "longitude": lon,
            "timezone": timezone or "auto",
            "current": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "weather_code",
                "wind_speed_10m",
                "surface_pressure",
            ]),
            "hourly": ",".join([
                "temperature_2m",
                "weather_code",
                "uv_index",
                "precipitation_probability",
                "visibility",
                "soil_moisture_0_to_1cm",
            ]),
            "daily": ",".join([
                "sunrise",
                "sunset",
                "temperature_2m_min",
                "uv_index_max",
                "precipitation_probability_max",
            ]),
            "forecast_days": 2,
        }
        return _get_json(FORECAST_URL, params, "Forecast request")

    return _cached_fetch(cache_key, do_fetch)


def fetch_air_quality(lat: float, lon: float, timezone: str) -> dict:
    cache_key = ("air_quality", round(lat, 3), round(lon, 3))

    def do_fetch():
        params = {
            "latitude": lat,
            "longitude": lon,
            "timezone": timezone or "auto",
            "current": "us_aqi,pm10,pm2_5",
            "hourly": "grass_pollen,birch_pollen,alder_pollen,ragweed_pollen",
        }
        return _get_json(AIR_QUALITY_URL, params, "Air quality request")

    return _cached_fetch(cache_key, do_fetch)


def fetch_marine(lat: float, lon: float, timezone: str) -> dict:
    """Only returns usable data for coastal/ocean coordinates. For inland
    locations Open-Meteo returns an empty hourly block — that's a stable
    geographic fact, so it's cached like any other result rather than
    treated as an error; the caller (data.py) checks for missing
    wave_height/water_temp and decides what that means."""
    cache_key = ("marine", round(lat, 3), round(lon, 3))

    def do_fetch():
        params = {
            "latitude": lat,
            "longitude": lon,
            "timezone": timezone or "auto",
            "hourly": "wave_height,sea_surface_temperature",
        }
        return _get_json(MARINE_URL, params, "Marine request")

    return _cached_fetch(cache_key, do_fetch)
