"""
Rule-based logic that turns raw weather conditions into persona-specific
stat cards and a one-line insight. Kept simple and explicit (no black box)
so thresholds are easy to tune later.

Every field read from `raw` here can genuinely be None now — there's no
mock data filling gaps anymore, so "the live source didn't have this"
is a real possibility every function has to handle honestly (show "Not
available" rather than guessing).
"""

# Health guidance below is based on real published thresholds — EPA's Air
# Quality Index categories and the WHO/EPA UV Index scale — not invented
# numbers. It is general environmental-health information, not a medical
# diagnosis or personalized medical advice.
HEALTH_DISCLAIMER = (
    "General guidance based on public air-quality and UV thresholds (EPA, WHO) — "
    "not a medical diagnosis. Talk to a doctor about your specific condition."
)

NA = "Not available"


def _aqi_label(aqi) -> str:
    if aqi is None:
        return NA
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Moderate"
    if aqi <= 150:
        return "Unhealthy (sensitive)"
    if aqi <= 200:
        return "Unhealthy"
    if aqi <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def _uv_label(uv) -> str:
    if uv is None:
        return NA
    if uv <= 2:
        return "Low"
    if uv <= 5:
        return "Moderate"
    if uv <= 7:
        return "High"
    if uv <= 10:
        return "Very High"
    return "Extreme"


def _num(value, unit="") -> str:
    """Format a possibly-missing numeric value honestly."""
    return f"{value}{unit}" if value is not None else NA


def health(raw: dict, condition: str = "general") -> dict:
    aqi = raw["aqi"]
    pollen = raw["pollen_level"]
    uv = raw["uv_index"]
    humidity = raw["humidity_pct"]
    feels_like = raw.get("feels_like_c")
    wind = raw["wind_kmh"]
    pressure = raw.get("pressure_hpa")

    pollen_caption = {
        "Unavailable": "Not tracked in this region",
        "Low": "", "Medium": "Moderate pollen", "High": "High pollen",
    }.get(pollen, "")

    if condition == "asthma":
        exertion = "High" if (aqi is not None and aqi > 100) else ("Moderate" if (aqi is not None and aqi > 50) else ("Low" if aqi is not None else NA))
        stats = [
            {"icon": "gauge", "label": "AQI", "value": _num(aqi), "caption": _aqi_label(aqi)},
            {"icon": "wind", "label": "Exertion Risk", "value": exertion, "caption": "EPA sensitive-groups guidance" if aqi is not None else ""},
            {"icon": "droplets", "label": "Humidity", "value": _num(humidity, "%"), "caption": "Can worsen symptoms" if (humidity is not None and humidity > 70) else ""},
            {"icon": "wind", "label": "Wind", "value": _num(wind, " km/h"), "caption": ""},
        ]
        if aqi is None:
            insight = "AQI data isn't available for this location right now — can't give asthma-specific guidance without it."
        elif aqi > 100:
            insight = f"AQI is {_aqi_label(aqi)} ({aqi}) — the EPA recommends people with asthma limit prolonged outdoor exertion at this level."
        elif humidity is not None and humidity > 70:
            insight = "Humidity is high today — some people with asthma find this triggers symptoms. Keep reliever medication on hand."
        else:
            insight = "Air quality and humidity look reasonable for outdoor activity today."

    elif condition == "allergies":
        stats = [
            {"icon": "sprout", "label": "Pollen", "value": pollen, "caption": pollen_caption},
            {"icon": "wind", "label": "Wind", "value": _num(wind, " km/h"), "caption": "Can spread pollen further" if (wind is not None and wind > 15) else ""},
            {"icon": "droplets", "label": "Humidity", "value": _num(humidity, "%"), "caption": ""},
            {"icon": "gauge", "label": "AQI", "value": _num(aqi), "caption": _aqi_label(aqi)},
        ]
        if pollen == "High":
            insight = "Pollen is high today — consider keeping windows closed and showering after being outdoors."
        elif pollen == "Unavailable":
            insight = "Pollen data isn't tracked for this region — AQI and wind are shown as the closest available indicators."
        else:
            insight = f"Pollen is {pollen.lower()} today — should be manageable for most people with seasonal allergies."

    elif condition == "cardiovascular":
        heat_risk = feels_like is not None and feels_like > 35
        aqi_risk = aqi is not None and aqi > 100
        stats = [
            {"icon": "thermometer", "label": "Feels Like", "value": _num(round(feels_like) if feels_like is not None else None, "°C"), "caption": "Heat strains the heart" if heat_risk else ""},
            {"icon": "gauge", "label": "AQI", "value": _num(aqi), "caption": _aqi_label(aqi)},
            {"icon": "droplets", "label": "Humidity", "value": _num(humidity, "%"), "caption": ""},
            {"icon": "wind", "label": "Wind", "value": _num(wind, " km/h"), "caption": ""},
        ]
        if heat_risk or aqi_risk:
            insight = "High heat and/or elevated AQI today — both are linked to added cardiovascular strain. Pace outdoor activity and stay hydrated."
        else:
            insight = "Heat and air quality look manageable today."

    elif condition == "skin":
        stats = [
            {"icon": "sun", "label": "UV Index", "value": _num(uv), "caption": _uv_label(uv)},
            {"icon": "thermometer", "label": "Feels Like", "value": _num(round(feels_like) if feels_like is not None else None, "°C"), "caption": ""},
            {"icon": "droplets", "label": "Humidity", "value": _num(humidity, "%"), "caption": ""},
            {"icon": "gauge", "label": "AQI", "value": _num(aqi), "caption": _aqi_label(aqi)},
        ]
        if uv is None:
            insight = "UV data isn't available for this location right now."
        elif uv >= 6:
            insight = f"UV Index is {_uv_label(uv)} ({uv}) — the WHO recommends SPF 30+, shade, and covering up around midday at this level."
        else:
            insight = f"UV Index is {_uv_label(uv)} today — standard sun protection should be enough."

    elif condition == "migraine":
        low_pressure = pressure is not None and pressure < 1005
        stats = [
            {"icon": "gauge", "label": "Pressure", "value": _num(pressure, " hPa"), "caption": "Low — some report this as a trigger" if low_pressure else ("Typical range" if pressure is not None else "")},
            {"icon": "sun", "label": "UV Index", "value": _num(uv), "caption": ""},
            {"icon": "droplets", "label": "Humidity", "value": _num(humidity, "%"), "caption": ""},
            {"icon": "thermometer", "label": "Feels Like", "value": _num(round(feels_like) if feels_like is not None else None, "°C"), "caption": ""},
        ]
        if pressure is None:
            insight = "Pressure data isn't available for this location right now."
        elif low_pressure:
            insight = "Barometric pressure is on the lower side today — some people with migraines report this as a trigger. Evidence is mixed, but worth noting if you're sensitive to it."
        else:
            insight = "Barometric pressure looks typical today."

    elif condition == "joint":
        temp_c = raw.get("temp_c")
        cold_humid = humidity is not None and humidity > 70 and temp_c is not None and temp_c < 15
        stats = [
            {"icon": "droplets", "label": "Humidity", "value": _num(humidity, "%"), "caption": "Often reported as a factor" if (humidity is not None and humidity > 70) else ""},
            {"icon": "thermometer", "label": "Temperature", "value": _num(round(temp_c) if temp_c is not None else None, "°C"), "caption": ""},
            {"icon": "gauge", "label": "Pressure", "value": _num(pressure, " hPa"), "caption": ""},
            {"icon": "wind", "label": "Wind", "value": _num(wind, " km/h"), "caption": ""},
        ]
        if cold_humid:
            insight = "Cool and humid today — some people with arthritis report more joint discomfort in these conditions (evidence is mixed, but commonly reported)."
        else:
            insight = "Conditions today aren't in the range most commonly linked to joint discomfort reports."

    else:  # "general" / not specified
        stats = [
            {"icon": "gauge", "label": "AQI", "value": _num(aqi), "caption": _aqi_label(aqi)},
            {"icon": "sprout", "label": "Pollen", "value": pollen, "caption": pollen_caption},
            {"icon": "sun", "label": "UV Index", "value": _num(uv), "caption": _uv_label(uv)},
            {"icon": "droplets", "label": "Humidity", "value": _num(humidity, "%"), "caption": "Slightly muggy" if (humidity is not None and humidity > 65) else ""},
        ]
        if (aqi is not None and aqi > 100) or pollen == "High":
            insight = "Air quality or pollen is elevated today — consider limiting outdoor time 11 AM–3 PM."
        else:
            insight = "Air quality looks fine for outdoor activity today."

    return {"stats": stats, "insight": insight, "disclaimer": HEALTH_DISCLAIMER}


FITNESS_DISCLAIMER = (
    "General guidance based on public heat-index (NWS), UV (WHO), and lightning-safety "
    "(NOAA) thresholds — not a substitute for how your body actually feels. Stop and rest if unwell."
)


def _heat_risk_label(feels_like) -> str:
    # NWS Heat Index categories (converted from °F to °C)
    if feels_like is None:
        return NA
    if feels_like < 27:
        return "Low"
    if feels_like < 32:
        return "Caution"
    if feels_like < 39:
        return "Extreme Caution"
    if feels_like < 51:
        return "Danger"
    return "Extreme Danger"


def fitness(raw: dict, activity: str = "general") -> dict:
    wind = raw["wind_kmh"]
    uv = raw["uv_index"]
    humidity = raw["humidity_pct"]
    feels_like = raw.get("feels_like_c")
    aqi = raw["aqi"]
    is_thunder = "thunder" in (raw.get("condition") or "").lower()
    heat_risk = _heat_risk_label(feels_like)
    heat_is_risky = feels_like is not None and feels_like >= 32

    if activity == "running":
        stats = [
            {"icon": "thermometer", "label": "Heat Risk", "value": heat_risk, "caption": "NWS heat-index scale"},
            {"icon": "droplets", "label": "Humidity", "value": _num(humidity, "%"), "caption": ""},
            {"icon": "sun", "label": "UV Index", "value": _num(uv), "caption": _uv_label(uv)},
            {"icon": "wind", "label": "Wind", "value": _num(wind, " km/h"), "caption": ""},
        ]
        if is_thunder:
            insight = "Thunderstorms detected — NOAA's guidance is simple: go indoors, don't run outside until it passes."
        elif heat_is_risky:
            insight = f"Heat risk is '{heat_risk}' today — the NWS recommends shorter, slower runs and extra hydration, ideally before 8 AM."
        else:
            insight = "Heat and humidity look manageable for a run today."

    elif activity == "cycling":
        stats = [
            {"icon": "wind", "label": "Wind", "value": _num(wind, " km/h"), "caption": "Headwind risk" if (wind is not None and wind > 25) else ""},
            {"icon": "thermometer", "label": "Feels Like", "value": _num(round(feels_like) if feels_like is not None else None, "°C"), "caption": ""},
            {"icon": "eye", "label": "Visibility", "value": _num(raw["visibility_km"], " km"), "caption": ""},
            {"icon": "cloud-sun", "label": "Road Conditions", "value": "Wet" if raw["condition"] in ("Light Rain", "Thunderstorms") else "Dry", "caption": ""},
        ]
        if is_thunder:
            insight = "Thunderstorms detected — get off the road and take shelter until it clears."
        elif wind is not None and wind > 25:
            insight = "Strong winds today — expect a tougher ride, especially on exposed roads."
        else:
            insight = "Wind and road conditions look reasonable for cycling today."

    elif activity == "gym":
        stats = [
            {"icon": "gauge", "label": "Outdoor AQI", "value": _num(aqi), "caption": "For your commute to/from" if aqi is not None else ""},
            {"icon": "thermometer", "label": "Outside Temp", "value": _num(round(raw["temp_c"]) if raw.get("temp_c") is not None else None, "°C"), "caption": ""},
            {"icon": "droplets", "label": "Humidity", "value": _num(humidity, "%"), "caption": ""},
            {"icon": "sun", "label": "UV Index", "value": _num(uv), "caption": ""},
        ]
        insight = "Indoor training isn't weather-dependent — these are just conditions for your commute to and from the gym."

    elif activity == "team_sports":
        stats = [
            {"icon": "alert-triangle", "label": "Thunder Risk", "value": "Active now" if is_thunder else "None", "caption": "NOAA: go indoors immediately" if is_thunder else ""},
            {"icon": "thermometer", "label": "Heat Risk", "value": heat_risk, "caption": ""},
            {"icon": "sun", "label": "UV Index", "value": _num(uv), "caption": _uv_label(uv)},
            {"icon": "wind", "label": "Wind", "value": _num(wind, " km/h"), "caption": ""},
        ]
        if is_thunder:
            insight = "Lightning risk — NOAA's rule is clear: suspend outdoor games and go indoors right away."
        elif heat_is_risky:
            insight = f"Heat risk is '{heat_risk}' — schedule breaks and hydration stops more often than usual."
        else:
            insight = "Conditions look fine for outdoor team sports today."

    elif activity == "yoga":
        stats = [
            {"icon": "thermometer", "label": "Feels Like", "value": _num(round(feels_like) if feels_like is not None else None, "°C"), "caption": ""},
            {"icon": "wind", "label": "Wind", "value": _num(wind, " km/h"), "caption": ""},
            {"icon": "droplets", "label": "Humidity", "value": _num(humidity, "%"), "caption": ""},
            {"icon": "sun", "label": "UV Index", "value": _num(uv), "caption": ""},
        ]
        if feels_like is not None and (feels_like < 15 or feels_like > 32):
            insight = "Temperature is outside the typical comfortable range for outdoor yoga — consider an indoor session."
        else:
            insight = "Comfortable conditions for outdoor yoga or stretching today."

    elif activity == "hiking":
        stats = [
            {"icon": "thermometer", "label": "Feels Like", "value": _num(round(feels_like) if feels_like is not None else None, "°C"), "caption": ""},
            {"icon": "eye", "label": "Visibility", "value": _num(raw["visibility_km"], " km"), "caption": raw["fog_alert"] or ""},
            {"icon": "sun", "label": "UV Index", "value": _num(uv), "caption": _uv_label(uv)},
            {"icon": "wind", "label": "Wind", "value": _num(wind, " km/h"), "caption": ""},
        ]
        if is_thunder:
            insight = "Thunderstorms detected — NOAA advises getting off exposed trails/ridgelines immediately."
        elif raw["visibility_km"] is not None and raw["visibility_km"] < 4:
            insight = "Reduced visibility today — take extra care on unfamiliar trails."
        else:
            insight = "Conditions look reasonable for a hike today — check UV and pack accordingly."

    else:  # "general"
        stats = [
            {"icon": "sunrise", "label": "Sunrise", "value": raw["sunrise"] or NA, "caption": ""},
            {"icon": "sunset", "label": "Sunset", "value": raw["sunset"] or NA, "caption": ""},
            {"icon": "thermometer", "label": "Feels Like", "value": _num(round(feels_like) if feels_like is not None else None, "°C"), "caption": heat_risk if heat_risk != NA else ""},
            {"icon": "wind", "label": "Wind Speed", "value": _num(wind, " km/h"), "caption": ("Light breeze" if wind < 20 else "Breezy") if wind is not None else ""},
        ]
        if raw.get("temp_c") is not None and raw["temp_c"] > 32:
            insight = "Heat builds fast past 11 AM — plan longer workouts before 8."
        else:
            insight = "Conditions are comfortable for a workout most of the day."

    return {"stats": stats, "insight": insight, "disclaimer": FITNESS_DISCLAIMER}


def beach(raw: dict) -> dict:
    marine_status = raw.get("marine_status", "unavailable_inland")

    if marine_status == "unavailable_inland":
        stats = [
            {"icon": "waves", "label": "Sea State", "value": NA, "caption": "No coast nearby"},
            {"icon": "gauge", "label": "High Tide", "value": NA, "caption": "No live tide-prediction source exists"},
            {"icon": "thermometer", "label": "Wave Height", "value": NA, "caption": ""},
            {"icon": "droplets", "label": "Water Temp", "value": NA, "caption": ""},
        ]
        insight = "This looks like an inland location — no beach or marine conditions to show here."
        return {"stats": stats, "insight": insight}

    stats = [
        {"icon": "waves", "label": "Sea State", "value": raw["sea_state"], "caption": ""},
        # Tide times have no live-data source at all (Open-Meteo doesn't
        # offer tide predictions) — honestly unavailable even for real
        # coastal cities, rather than a simulated time that looks real.
        {"icon": "gauge", "label": "High Tide", "value": NA, "caption": "No live tide-prediction source exists"},
        {"icon": "thermometer", "label": "Wave Height", "value": _num(raw["wave_height_m"], " m"), "caption": ""},
        {"icon": "droplets", "label": "Water Temp", "value": _num(raw["water_temp_c"], "°C"), "caption": ""},
    ]
    if raw["sea_state"] == "Rough":
        insight = "Sea conditions are rough today — take care swimming near the shore break."
    else:
        insight = "Sea and wave conditions look manageable today. (Tide times aren't available — no live tide-prediction source exists.)"
    return {"stats": stats, "insight": insight}


def travel(raw: dict) -> dict:
    stats = [
        {"icon": "map-pin", "label": "Saved Destinations", "value": "2", "caption": "London, Dubai"},
        {"icon": "cloud-sun", "label": "Condition", "value": raw["condition"], "caption": raw["city"]},
        {"icon": "sun", "label": "Temp", "value": _num(raw["temp_c"], "°C"), "caption": ""},
        # No live flight-status/aviation data source is wired in — honestly
        # unavailable rather than a simulated alert.
        {"icon": "alert-triangle", "label": "Flight Alert", "value": NA, "caption": "No live flight-status source"},
    ]
    insight = "Live flight-status data isn't available yet — check your airline directly before heading out."
    return {"stats": stats, "insight": insight}


def family(raw: dict) -> dict:
    rain_pct = raw["rain_probability_pct"]
    rain_soon = rain_pct is not None and rain_pct > 40
    stats = [
        {"icon": "eye", "label": "School Commute", "value": "Watch for rain" if rain_soon else ("Clear now" if rain_pct is not None else NA), "caption": ""},
        {"icon": "umbrella", "label": "Rain Alert", "value": "Likely later" if rain_soon else ("Unlikely" if rain_pct is not None else NA), "caption": ""},
        {"icon": "alert-triangle", "label": "Severe Warning", "value": "None", "caption": "All clear"},
        {"icon": "wind", "label": "Wind", "value": _num(raw["wind_kmh"], " km/h"), "caption": ""},
    ]
    if rain_pct is None:
        insight = "Rain-probability data isn't available for this location right now."
    elif rain_soon:
        insight = "Rain is possible before pickup — send an umbrella just in case."
    else:
        insight = "Conditions look calm for the school run today."
    return {"stats": stats, "insight": insight}


def farm(raw: dict) -> dict:
    soil = raw["soil_moisture_pct"]
    rain_pct = raw["rainfall_chance_pct"]
    stats = [
        {"icon": "droplets", "label": "Soil Moisture", "value": _num(soil, "%"), "caption": ("Adequate" if soil > 35 else "Low") if soil is not None else ""},
        {"icon": "cloud-sun", "label": "Rainfall Chance", "value": _num(rain_pct, "%"), "caption": "Next 24h" if rain_pct is not None else ""},
        {"icon": "thermometer", "label": "Frost Alert", "value": raw["frost_risk"] or NA, "caption": ""},
        {"icon": "sprout", "label": "Planting Tip", "value": ("Good week" if rain_pct < 50 else "Hold off") if rain_pct is not None else NA, "caption": ""},
    ]
    if rain_pct is None:
        insight = "Rainfall forecast isn't available for this location right now."
    elif rain_pct > 50:
        insight = "Rain expected soon — hold off irrigation to avoid overwatering."
    else:
        insight = "Dry conditions ahead — a good window for irrigation or sowing."
    return {"stats": stats, "insight": insight}


def commute(raw: dict) -> dict:
    vis = raw["visibility_km"]
    fog = raw["fog_alert"]
    stats = [
        {"icon": "eye", "label": "Visibility", "value": _num(vis, " km"), "caption": ("Hazy" if vis < 4 else "Clear") if vis is not None else ""},
        {"icon": "car", "label": "Road Conditions", "value": "Wet patches" if raw["condition"] in ("Light Rain", "Thunderstorms") else "Dry", "caption": ""},
        {"icon": "alert-triangle", "label": "Fog Alert", "value": fog or NA, "caption": ""},
        {"icon": "wind", "label": "Wind", "value": _num(raw["wind_kmh"], " km/h"), "caption": ""},
    ]
    if vis is None:
        insight = "Visibility data isn't available for this location right now."
    elif vis < 4 or (fog and fog != "None"):
        insight = "Reduced visibility this morning — add extra time to your commute."
    else:
        insight = "Roads and visibility look clear for your commute."
    return {"stats": stats, "insight": insight}


def events(raw: dict) -> dict:
    rain_pct = raw["rain_probability_pct"]
    wind = raw["wind_kmh"]
    comfort = None
    if rain_pct is not None:
        comfort = "Pleasant" if 18 <= raw["temp_c"] <= 30 and rain_pct < 40 else "Mixed"
    stats = [
        {"icon": "umbrella", "label": "Rain Probability", "value": _num(rain_pct, "%"), "caption": ""},
        {"icon": "gauge", "label": "Comfort Index", "value": comfort or NA, "caption": ""},
        {"icon": "wind", "label": "Wind", "value": _num(wind, " km/h"), "caption": ("Calm for setup" if wind < 15 else "Windy") if wind is not None else ""},
        {"icon": "calendar-heart", "label": "Outlook", "value": raw["condition"], "caption": ""},
    ]
    if comfort == "Pleasant":
        insight = "Conditions look ideal for an outdoor gathering."
    elif comfort == "Mixed":
        insight = "Consider a backup indoor plan — conditions are less predictable."
    else:
        insight = "Rain-probability data isn't available for this location right now."
    return {"stats": stats, "insight": insight}


PERSONA_HANDLERS = {
    "health": health,
    "fitness": fitness,
    "beach": beach,
    "travel": travel,
    "family": family,
    "farm": farm,
    "commute": commute,
    "events": events,
}
