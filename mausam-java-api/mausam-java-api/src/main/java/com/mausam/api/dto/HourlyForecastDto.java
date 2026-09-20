package com.mausam.api.dto;

import java.util.List;

public record HourlyForecastDto(
        String city,
        List<HourlyPointDto> hours
) {}
