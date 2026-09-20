package com.mausam.api.service;

import com.mausam.api.model.Persona;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.Optional;

@Service
public class PersonaCatalog {

    private final List<Persona> personas = List.of(
            new Persona("health", "Health", "heart-pulse", "#2F6E68", "#E4EFEC"),
            new Persona("fitness", "Fitness", "footprints", "#C98A2C", "#F6EBDA"),
            new Persona("beach", "Beach", "waves", "#2E5A82", "#E3EBF2"),
            new Persona("travel", "Travel", "plane", "#B5502F", "#F2E2DB"),
            new Persona("family", "Family", "users", "#7A5B8C", "#EBE4F0"),
            new Persona("farm", "Farm", "sprout", "#5B7F3A", "#E9EFE0"),
            new Persona("commute", "Commute", "car", "#3B6E96", "#E2ECF2"),
            new Persona("events", "Events", "calendar-heart", "#A87A2E", "#F2E9D8")
    );

    private final Map<String, Persona> byId = personas.stream()
            .collect(java.util.stream.Collectors.toMap(Persona::id, p -> p));

    public List<Persona> all() {
        return personas;
    }

    public Optional<Persona> find(String id) {
        return Optional.ofNullable(byId.get(id));
    }

    public boolean exists(String id) {
        return byId.containsKey(id);
    }
}
