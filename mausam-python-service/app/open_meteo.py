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

# PERFORMANCE: one /api/home request from the frontend triggers three
# separate calls into this service (current weather, hourly, persona
# metrics) — each of which independently needs forecast/air-quality/
# marine data for the same location. Without caching, that's the same
# Open-Meteo data fetched 2-3x over for a single screen load: slower,
# and more surface area for a transient network hiccup to break the
# whole response. This cache means only the first of those calls
# actually reaches Open-Meteo; the other two reuse the same result.
# TTL is short (90s) — long enough to cover those near-simultaneous
# calls, short enough that weather data doesn't go stale. Only
# successful results are ever cached — a failure is never remembered,
# so the next call always retries for real.
_fetch_cache: dict = {}
CACHE_TTL_SECONDS = 900


def _cached_fetch(cache_key, fetch_fn):
    now = time.time()
    entry = _fetch_cache.get(cache_key)
    if entry is not None and entry[0] > now:
        return entry[1]
    result = fetch_fn()
    _fetch_cache[cache_key] = (now + CACHE_TTL_SECONDS, result)
    return result


class OpenMeteoError(Exception):
    pass


def _get_json(url: str, params: dict, what: str) -> dict:
    """GET JSON with limited retry/backoff."""

    last_error = None

    for attempt in range(2):
        try:
            resp = requests.get(
                url,
                params=params,
                timeout=TIMEOUT_SECONDS
            )

            if resp.status_code == 429:
                if attempt == 0:
                    time.sleep(10)
                    continue

                raise OpenMeteoError(
                    f"{what} was rate limited by Open-Meteo (HTTP 429). "
                    "Please try again shortly."
                )

            resp.raise_for_status()
            return resp.json()

        except OpenMeteoError:
            raise

        except requests.RequestException as exc:
            last_error = exc

            if attempt == 0:
                time.sleep(2)

    raise OpenMeteoError(
        f"{what} failed after retry: {last_error}"
    ) from last_error


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
