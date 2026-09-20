package com.mausam.api.controller;

import com.mausam.api.model.Location;
import com.mausam.api.service.LocationDirectory;
import com.mausam.api.service.WeatherDataClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/locations")
public class LocationController {

    private final LocationDirectory locationDirectory;
    private final WeatherDataClient weatherDataClient;

    public LocationController(LocationDirectory locationDirectory, WeatherDataClient weatherDataClient) {
        this.locationDirectory = locationDirectory;
        this.weatherDataClient = weatherDataClient;
    }

    @GetMapping
    public List<Location> search(@RequestParam(name = "q", required = false) String query) {
        // No query yet (dropdown just opened) — show the curated popular-cities
        // list, which is instant and needs no network round-trip.
        if (query == null || query.isBlank()) {
            return locationDirectory.all();
        }

        // Real query — search globally (cities, towns, villages worldwide),
        // not just our 10-city curated list.
        List<Location> globalResults = weatherDataClient.searchLocations(query, 10);
        if (!globalResults.isEmpty()) {
            return globalResults;
        }

        // Global search unavailable or found nothing — fall back to filtering
        // the local curated list so the dropdown still shows something useful
        // for well-known cities even if the Python service is unreachable.
        return locationDirectory.search(query);
    }
}
