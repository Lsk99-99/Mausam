package com.mausam.api.controller;

import com.mausam.api.dto.HomeResponse;
import com.mausam.api.model.Location;
import com.mausam.api.service.LocationDirectory;
import com.mausam.api.service.PersonaCatalog;
import com.mausam.api.service.WeatherDataClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;

@RestController
public class HomeController {

    private final PersonaCatalog personaCatalog;
    private final LocationDirectory locationDirectory;
    private final WeatherDataClient weatherDataClient;

    public HomeController(
            PersonaCatalog personaCatalog,
            LocationDirectory locationDirectory,
            WeatherDataClient weatherDataClient
    ) {
        this.personaCatalog = personaCatalog;
        this.locationDirectory = locationDirectory;
        this.weatherDataClient = weatherDataClient;
    }

    /**
     * Single call the mobile app makes on load / when the user switches
     * persona or city. Aggregates the persona catalog (static) with live
     * data from the Python weather-data service.
     */
    @GetMapping("/api/home")
    public HomeResponse home(
            @RequestParam(defaultValue = "Mumbai") String city,
            @RequestParam(defaultValue = "health") String persona,
            @RequestParam(required = false) String condition,
            @RequestParam(required = false) String activity,
            @RequestParam(required = false) Double lat,
            @RequestParam(required = false) Double lon
    ) {
        if (!personaCatalog.exists(persona)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Unknown persona '" + persona + "'");
        }

        Location location = locationDirectory.all().stream()
                .filter(l -> l.city().equalsIgnoreCase(city))
                .findFirst()
                .orElse(new Location(city, "", lat, lon));

        // Prefer explicit lat/lon from the request (a search result the
        // frontend is passing through) over whatever the curated list has,
        // since the caller's coordinates are for the specific place they
        // actually selected.
        Double useLat = lat != null ? lat : location.latitude();
        Double useLon = lon != null ? lon : location.longitude();

        var currentWeather = weatherDataClient.getCurrentWeather(location.city(), useLat, useLon);
        var hourly = weatherDataClient.getHourly(location.city(), 6, useLat, useLon);
        var personaMetrics = weatherDataClient.getPersonaMetrics(persona, location.city(), condition, activity, useLat, useLon);

        return new HomeResponse(
                location,
                personaCatalog.all(),
                persona,
                currentWeather,
                hourly,
                personaMetrics
        );
    }
}
