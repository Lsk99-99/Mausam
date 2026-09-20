package com.mausam.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

public record PersonaMetricsDto(
        @JsonProperty("persona_id") String personaId,
        String city,
        List<StatItemDto> stats,
        String insight,
        @JsonProperty("is_live") boolean isLive,
        String disclaimer
) {}
