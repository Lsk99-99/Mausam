package com.mausam.api.service;

import com.mausam.api.model.Location;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class LocationDirectory {

    private final List<Location> locations = List.of(
            new Location("Mumbai", "Maharashtra", 19.0760, 72.8777),
            new Location("Delhi", "NCT", 28.7041, 77.1025),
            new Location("Bengaluru", "Karnataka", 12.9716, 77.5946),
            new Location("Kolkata", "West Bengal", 22.5726, 88.3639),
            new Location("Jaipur", "Rajasthan", 26.9124, 75.7873),
            new Location("Chennai", "Tamil Nadu", 13.0827, 80.2707),
            new Location("Pune", "Maharashtra", 18.5204, 73.8567),
            new Location("Hyderabad", "Telangana", 17.3850, 78.4867),
            new Location("Ahmedabad", "Gujarat", 23.0225, 72.5714),
            new Location("Lucknow", "Uttar Pradesh", 26.8467, 80.9462)
    );

    public List<Location> all() {
        return locations;
    }

    public List<Location> search(String query) {
        if (query == null || query.isBlank()) {
            return locations;
        }
        String needle = query.toLowerCase();
        return locations.stream()
                .filter(l -> (l.city() + " " + l.region()).toLowerCase().contains(needle))
                .toList();
    }

    public boolean isKnownCity(String city) {
        return locations.stream().anyMatch(l -> l.city().equalsIgnoreCase(city));
    }
}
