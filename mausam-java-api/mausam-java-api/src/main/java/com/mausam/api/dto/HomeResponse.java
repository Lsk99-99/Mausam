package com.mausam.api.dto;

import com.mausam.api.model.Location;
import com.mausam.api.model.Persona;

import java.util.List;

public record HomeResponse(
        Location location,
        List<Persona> personas,
        String activePersonaId,
        CurrentWeatherDto currentWeather,
        HourlyForecastDto hourly,
        PersonaMetricsDto personaMetrics
) {}
