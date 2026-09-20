package com.mausam.api.model;

public record Location(String city, String region, Double latitude, Double longitude) {
    // Convenience constructor for the curated list, where coordinates
    // aren't tracked — falls back to name-based geocoding, which is fine
    // for well-known major cities.
    public Location(String city, String region) {
        this(city, region, null, null);
    }
}
