import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.data import get_raw_conditions, get_hourly
from app.insights import PERSONA_HANDLERS
from app.models import CurrentWeather, HourlyForecast, PersonaMetrics
from app import open_meteo

logger = logging.getLogger("mausam.weather")
router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/current", response_model=CurrentWeather)
def current_weather(
    city: str = Query(..., description="City name, e.g. Mumbai"),
    lat: Optional[float] = Query(None, description="Latitude, if already known from a search result — avoids re-geocoding by name"),
    lon: Optional[float] = Query(None, description="Longitude, if already known from a search result"),
):
    try:
        raw = get_raw_conditions(city, lat, lon)
    except open_meteo.OpenMeteoError as exc:
        # SECURITY: log the real internal exception server-side only —
        # don't hand raw connection/library exception text to API
        # clients, it can reveal internal details for no real benefit.
        logger.warning("Live weather fetch failed for '%s': %s", city, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Couldn't reach live weather data for '{city}' right now. Try again in a moment.",
        )
    return CurrentWeather(
        city=raw["city"],
        temp_c=raw["temp_c"],
        feels_like_c=raw["feels_like_c"],
        condition=raw["condition"],
        humidity_pct=raw["humidity_pct"],
        wind_kmh=raw["wind_kmh"],
        is_live=raw.get("is_live", False),
    )


@router.get("/hourly", response_model=HourlyForecast)
def hourly_forecast(
    city: str = Query(...),
    hours: int = Query(6, ge=1, le=24),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
):
    try:
        points = get_hourly(city, hours, lat, lon)
    except open_meteo.OpenMeteoError as exc:
        logger.warning("Live hourly fetch failed for '%s': %s", city, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Couldn't reach live hourly forecast for '{city}' right now. Try again in a moment.",
        )
    return HourlyForecast(city=city, hours=points)


@router.get("/persona/{persona_id}", response_model=PersonaMetrics)
def persona_metrics(
    persona_id: str,
    city: str = Query(...),
    condition: Optional[str] = Query(None, description="For persona=health only: asthma, allergies, cardiovascular, skin, migraine, joint, or general"),
    activity: Optional[str] = Query(None, description="For persona=fitness only: running, cycling, gym, team_sports, yoga, hiking, or general"),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
):
    handler = PERSONA_HANDLERS.get(persona_id)
    if handler is None:
        raise HTTPException(status_code=404, detail=f"Unknown persona '{persona_id}'")

    try:
        raw = get_raw_conditions(city, lat, lon)
    except open_meteo.OpenMeteoError as exc:
        logger.warning("Live weather fetch failed for '%s': %s", city, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Couldn't reach live weather data for '{city}' right now. Try again in a moment.",
        )

    if persona_id == "health":
        result = handler(raw, condition or "general")
    elif persona_id == "fitness":
        result = handler(raw, activity or "general")
    else:
        result = handler(raw)
    return PersonaMetrics(
        persona_id=persona_id,
        city=city,
        stats=result["stats"],
        insight=result["insight"],
        is_live=raw.get("is_live", False),
        disclaimer=result.get("disclaimer"),
    )


location_router = APIRouter(prefix="/locations", tags=["locations"])


@location_router.get("/search")
def location_search(q: str = Query(..., min_length=1), limit: int = Query(8, ge=1, le=20)):
    """Global city/town/village search via Open-Meteo's geocoder — not
    limited to any fixed list. Returns [] (not an error) if nothing
    matches, so the frontend can show 'no cities found' cleanly."""
    try:
        return open_meteo.search_locations(q, count=limit)
    except open_meteo.OpenMeteoError:
        # Search truly unavailable (network down) — empty list lets the
        # frontend fall back to its own cached/suggested list gracefully.
        return []
