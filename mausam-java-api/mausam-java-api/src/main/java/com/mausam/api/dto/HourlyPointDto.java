package com.mausam.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record HourlyPointDto(
        String label,
        @JsonProperty("temp_c") double tempC,
        String condition
) {}
