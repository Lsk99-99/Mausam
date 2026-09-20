package com.mausam.api.controller;

import com.mausam.api.service.WeatherDataClient.WeatherServiceUnavailableException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.Map;

@RestControllerAdvice
public class ApiExceptionHandler {

    @ExceptionHandler(WeatherServiceUnavailableException.class)
    public ResponseEntity<Map<String, String>> handleWeatherServiceDown(WeatherServiceUnavailableException ex) {
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                .body(Map.of(
                        "error", "weather_service_unavailable",
                        "message", ex.getMessage()
                ));
    }
}
