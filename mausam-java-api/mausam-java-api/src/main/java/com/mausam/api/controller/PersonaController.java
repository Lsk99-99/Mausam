package com.mausam.api.controller;

import com.mausam.api.model.Persona;
import com.mausam.api.service.PersonaCatalog;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/personas")
public class PersonaController {

    private final PersonaCatalog personaCatalog;

    public PersonaController(PersonaCatalog personaCatalog) {
        this.personaCatalog = personaCatalog;
    }

    @GetMapping
    public List<Persona> listPersonas() {
        return personaCatalog.all();
    }
}
