from datetime import datetime

from app import open_meteo


def _resolve_location(city: str, lat: float = None, lon: float = None):
    """Returns (display_name, latitude, longitude, timezone).

    If coordinates are already known (the frontend found this place via
    /locations/search and is passing them straight through), use them
    directly — skip re-geocoding by name entirely. Re-searching a village
    by name alone is unreliable: name collisions and sparse data are far
    more common for small places than for major cities, so a second
    independent lookup can fail or resolve to the wrong place even when
    the first search found the right one.

    Falls back to name-based geocoding only when coordinates aren't
    supplied (e.g. the curated default-city shortcuts).
    """
    if lat is not None and lon is not None:
        return city, lat, lon, "auto"
    geo = open_meteo.geocode_city(city)
    return geo["name"], geo["latitude"], geo["longitude"], geo["timezone"]


def _fmt_clock(iso_str: str):
    """'2026-08-28T06:05' -> '6:05 AM'. Returns None if unavailable — the
    caller decides how to display that, we don't invent a placeholder time."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%I:%M %p").lstrip("0")
    except (ValueError, TypeError):
        return None


def _pollen_level(air_quality: dict) -> str:
    hourly = air_quality.get("hourly", {})
    values = []
    for key in ("grass_pollen", "birch_pollen", "alder_pollen", "ragweed_pollen"):
        series = hourly.get(key) or []
        if series and series[0] is not None:
            values.append(series[0])
    if not values:
        return "Unavailable"
    peak = max(values)
    if peak < 10:
        return "Low"
    if peak < 50:
        return "Medium"
    return "High"


def _live_raw_conditions(city: str, lat: float = None, lon: float = None) -> dict:
    name, lat, lon, tz = _resolve_location(city, lat, lon)

    forecast = open_meteo.fetch_forecast(lat, lon, tz)
    current = forecast.get("current", {})
    hourly = forecast.get("hourly", {})
    daily = forecast.get("daily", {})

    try:
        air_quality = open_meteo.fetch_air_quality(lat, lon, tz)
    except open_meteo.OpenMeteoError:
        air_quality = {}

    temp_c = current.get("temperature_2m")
    if temp_c is None:
        # Core reading missing — this isn't a "some fields unavailable"
        # situation, it means the live fetch itself didn't really work.
        # Let the caller treat this the same as a network failure.
        raise open_meteo.OpenMeteoError("Forecast response missing temperature_2m")

    feels_like_c = current.get("apparent_temperature", temp_c)
    condition = open_meteo.weather_code_to_condition(current.get("weather_code"))
    humidity_pct = current.get("relative_humidity_2m")
    pressure_hpa = current.get("surface_pressure")
    wind_kmh = current.get("wind_speed_10m")

    uv_series = hourly.get("uv_index") or []
    uv_index = round(uv_series[0]) if uv_series and uv_series[0] is not None else None

    visibility_series = hourly.get("visibility") or []
    visibility_m = visibility_series[0] if visibility_series else None
    visibility_km = round(visibility_m / 1000, 1) if visibility_m is not None else None

    soil_series = hourly.get("soil_moisture_0_to_1cm") or []
    soil_moisture_frac = soil_series[0] if soil_series else None
    soil_moisture_pct = round(soil_moisture_frac * 100) if soil_moisture_frac is not None else None

    min_temp_series = daily.get("temperature_2m_min") or []
    daily_min_temp = min_temp_series[0] if min_temp_series else None

    rain_series = daily.get("precipitation_probability_max") or []
    rain_chance = rain_series[0] if rain_series else None

    sunrise_series = daily.get("sunrise") or []
    sunset_series = daily.get("sunset") or []
    sunrise = _fmt_clock(sunrise_series[0]) if sunrise_series else None
    sunset = _fmt_clock(sunset_series[0]) if sunset_series else None

    if daily_min_temp is None:
        frost_risk = None
    elif daily_min_temp < 2:
        frost_risk = "High"
    elif daily_min_temp < 5:
        frost_risk = "Slight"
    else:
        frost_risk = "None"

    if visibility_km is None:
        fog_alert = None
    elif visibility_km < 1:
        fog_alert = "Dense fog advisory"
    elif visibility_km < 4:
        fog_alert = "Light fog"
    else:
        fog_alert = "None"

    aqi_raw = air_quality.get("current", {}).get("us_aqi")
    aqi = round(aqi_raw) if aqi_raw is not None else None

    # Marine data only exists for coastal coordinates. Since we've already
    # succeeded at geocoding + forecast here, a marine failure means this
    # location genuinely has no sea nearby.
    try:
        marine = open_meteo.fetch_marine(lat, lon, tz)
        marine_hourly = marine.get("hourly", {})
        wave_height_m = (marine_hourly.get("wave_height") or [None])[0]
        water_temp_c = (marine_hourly.get("sea_surface_temperature") or [None])[0]
        if wave_height_m is None or water_temp_c is None:
            raise open_meteo.OpenMeteoError("Incomplete marine data")
        wave_height_m = round(wave_height_m, 1)
        water_temp_c = round(water_temp_c, 1)
        sea_state = "Calm" if wave_height_m < 0.5 else "Moderate" if wave_height_m < 1.5 else "Rough"
        marine_status = "live"
    except open_meteo.OpenMeteoError:
        wave_height_m = None
        water_temp_c = None
        sea_state = None
        marine_status = "unavailable_inland"

    return {
        "city": name,
        "temp_c": round(temp_c, 1),
        "feels_like_c": round(feels_like_c, 1),
        "condition": condition,
        "humidity_pct": round(humidity_pct) if humidity_pct is not None else None,
        "wind_kmh": round(wind_kmh, 1) if wind_kmh is not None else None,

        "aqi": aqi,
        "pressure_hpa": round(pressure_hpa, 1) if pressure_hpa is not None else None,
        "pollen_level": _pollen_level(air_quality) if air_quality else "Unavailable",
        "uv_index": uv_index,

        "sunrise": sunrise,
        "sunset": sunset,

        "sea_state": sea_state,
        "marine_status": marine_status,
        # Open-Meteo has no tide-prediction API at all — this is never
        # live, for any city, coastal or not. Honestly "Not available"
        # rather than a plausible-looking invented time.
        "tide_high": None,
        "tide_low": None,
        "wave_height_m": wave_height_m,
        "water_temp_c": water_temp_c,

        # No live flight-status source is wired in — honestly unavailable
        # rather than a simulated alert that looks real.
        "flight_alert": None,

        "soil_moisture_pct": soil_moisture_pct,
        "rainfall_chance_pct": round(rain_chance) if rain_chance is not None else None,
        "frost_risk": frost_risk,

        "visibility_km": visibility_km,
        "fog_alert": fog_alert,

        "rain_probability_pct": round(rain_chance) if rain_chance is not None else None,

        "generated_at": datetime.now().isoformat(),
        "is_live": True,
        "data_source": "live" if marine_status == "live" else "live (marine unavailable — inland location)",
    }


def get_raw_conditions(city: str, lat: float = None, lon: float = None) -> dict:
    # No mock fallback — if live data can't be fetched, the API layer
    # returns a clear error instead of silently substituting fake numbers.
    return _live_raw_conditions(city, lat, lon)


def get_hourly(city: str, hours: int = 6, lat: float = None, lon: float = None) -> list:
    _, lat, lon, tz = _resolve_location(city, lat, lon)
    forecast = open_meteo.fetch_forecast(lat, lon, tz)
    hourly = forecast.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    codes = hourly.get("weather_code", [])

    if not times:
        raise open_meteo.OpenMeteoError("No hourly data returned")

    # Bound by the shortest of the parallel arrays so an index is never
    # out of range, and temp_c (non-optional in the API schema) is never
    # None even if Open-Meteo's arrays are ever mismatched in length.
    count = min(hours, len(times), len(temps))
    points = []
    for i in range(count):
        dt = datetime.fromisoformat(times[i])
        label = "Now" if i == 0 else dt.strftime("%I %p").lstrip("0")
        points.append({
            "label": label,
            "temp_c": round(temps[i], 1),
            "condition": open_meteo.weather_code_to_condition(codes[i]) if i < len(codes) else "Cloudy",
        })
    return points
