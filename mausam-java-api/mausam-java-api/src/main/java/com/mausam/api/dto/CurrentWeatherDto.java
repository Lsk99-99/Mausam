package com.mausam.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record CurrentWeatherDto(
        String city,
        @JsonProperty("temp_c") double tempC,
        @JsonProperty("feels_like_c") double feelsLikeC,
        String condition,
        @JsonProperty("humidity_pct") Integer humidityPct,
        @JsonProperty("wind_kmh") Double windKmh,
        @JsonProperty("is_live") boolean isLive
) {}
