package com.mausam.api.controller;

import com.mausam.api.dto.AuthDtos.AuthResponse;
import com.mausam.api.dto.AuthDtos.LoginRequest;
import com.mausam.api.dto.AuthDtos.SignupRequest;
import com.mausam.api.model.User;
import com.mausam.api.repository.UserRepository;
import com.mausam.api.security.JwtUtil;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtUtil jwtUtil;

    public AuthController(
            UserRepository userRepository,
            PasswordEncoder passwordEncoder,
            JwtUtil jwtUtil
    ) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtUtil = jwtUtil;
    }

    @PostMapping("/signup")
    public AuthResponse signup(@Valid @RequestBody SignupRequest request) {
        if (userRepository.existsByEmail(request.email())) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT,
                    "An account with this email already exists"
            );
        }

        User user = new User(
                request.name(),
                request.email(),
                passwordEncoder.encode(request.password())
        );

        userRepository.save(user);

        String token = jwtUtil.generateToken(user.getEmail());

        return new AuthResponse(
                token,
                user.getName(),
                user.getEmail()
        );
    }

    @PostMapping("/login")
    public AuthResponse login(@Valid @RequestBody LoginRequest request) {
        User user = userRepository.findByEmail(request.email())
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.UNAUTHORIZED,
                        "Invalid email or password"
                ));

        if (!passwordEncoder.matches(
                request.password(),
                user.getPasswordHash()
        )) {
            throw new ResponseStatusException(
                    HttpStatus.UNAUTHORIZED,
                    "Invalid email or password"
            );
        }

        String token = jwtUtil.generateToken(user.getEmail());

        return new AuthResponse(
                token,
                user.getName(),
                user.getEmail()
        );
    }

    @PostMapping("/guest")
    public AuthResponse guest() {
        final String guestEmail = "guest@mausam.demo";

        User guest = userRepository.findByEmail(guestEmail)
                .orElseGet(() -> {
                    User user = new User(
                            "Mausam Guest",
                            guestEmail,
                            passwordEncoder.encode(
                                    java.util.UUID.randomUUID().toString()
                            )
                    );

                    return userRepository.save(user);
                });

        String token = jwtUtil.generateToken(guest.getEmail());

        return new AuthResponse(
                token,
                guest.getName(),
                guest.getEmail()
        );
    }
}
