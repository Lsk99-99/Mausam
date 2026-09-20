package com.mausam.api.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.mausam.api.dto.CurrentWeatherDto;
import com.mausam.api.dto.HourlyForecastDto;
import com.mausam.api.dto.PersonaMetricsDto;
import com.mausam.api.model.Location;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.util.Arrays;
import java.util.List;

@Service
public class WeatherDataClient {

    private final RestTemplate restTemplate;
    private final String baseUrl;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public WeatherDataClient(
            RestTemplate restTemplate,
            @Value("${mausam.python-service.base-url:http://localhost:8000}") String baseUrl
    ) {
        this.restTemplate = restTemplate;
        this.baseUrl = baseUrl;
    }

    public CurrentWeatherDto getCurrentWeather(String city, Double lat, Double lon) {
        UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(baseUrl + "/weather/current")
                .queryParam("city", city);
        addCoords(builder, lat, lon);
        return callOrFail(builder.toUriString(), CurrentWeatherDto.class, "current weather");
    }

    public HourlyForecastDto getHourly(String city, int hours, Double lat, Double lon) {
        UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(baseUrl + "/weather/hourly")
                .queryParam("city", city)
                .queryParam("hours", hours);
        addCoords(builder, lat, lon);
        return callOrFail(builder.toUriString(), HourlyForecastDto.class, "hourly forecast");
    }

    public PersonaMetricsDto getPersonaMetrics(String personaId, String city, String condition, String activity, Double lat, Double lon) {
        UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(baseUrl + "/weather/persona/" + personaId)
                .queryParam("city", city);
        if (condition != null && !condition.isBlank()) {
            builder.queryParam("condition", condition);
        }
        if (activity != null && !activity.isBlank()) {
            builder.queryParam("activity", activity);
        }
        addCoords(builder, lat, lon);
        return callOrFail(builder.toUriString(), PersonaMetricsDto.class, "persona metrics");
    }

    /**
     * If coordinates are already known (the location came from a search
     * result), forward them so Python skips re-geocoding by name — more
     * reliable for villages/small towns, which are more prone to name
     * collisions or sparse geocoding data than major cities.
     */
    private void addCoords(UriComponentsBuilder builder, Double lat, Double lon) {
        if (lat != null && lon != null) {
            builder.queryParam("lat", lat).queryParam("lon", lon);
        }
    }

    /**
     * Global city/town/village search (not limited to any fixed list),
     * delegated to Python's Open-Meteo geocoder. Unlike the other calls
     * here, a failure returns an empty list instead of throwing — search
     * failing shouldn't break the whole app, the controller falls back
     * to the curated local directory instead.
     */
    public List<Location> searchLocations(String query, int limit) {
        String url = UriComponentsBuilder.fromHttpUrl(baseUrl + "/locations/search")
                .queryParam("q", query)
                .queryParam("limit", limit)
                .toUriString();
        try {
            Location[] results = restTemplate.getForObject(url, Location[].class);
            return results != null ? Arrays.asList(results) : List.of();
        } catch (RestClientException ex) {
            return List.of();
        }
    }

    private <T> T callOrFail(String url, Class<T> type, String what) {
        try {
            return restTemplate.getForObject(url, type);
        } catch (HttpStatusCodeException ex) {
            // Python responded, but with an error — e.g. 503 "live weather
            // data unavailable for this city right now". Forward its actual
            // message instead of a generic "is it running?" (it clearly is).
            String detail = extractDetail(ex.getResponseBodyAsString());
            String message = detail != null ? detail : ("Could not fetch " + what + " from the weather-data service");
            throw new WeatherServiceUnavailableException(message, ex);
        } catch (RestClientException ex) {
            // No HTTP response at all — connection refused, timeout, DNS
            // failure. This really does mean the service isn't reachable.
            throw new WeatherServiceUnavailableException(
                    "Could not fetch " + what + " — the weather-data service isn't reachable. Is it running on the configured port?", ex);
        }
    }

    private String extractDetail(String responseBody) {
        try {
            JsonNode node = objectMapper.readTree(responseBody);
            JsonNode detail = node.get("detail");
            return detail != null ? detail.asText() : null;
        } catch (Exception ex) {
            return null;
        }
    }

    public static class WeatherServiceUnavailableException extends RuntimeException {
        public WeatherServiceUnavailableException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}
