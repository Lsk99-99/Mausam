# Mausam Main API (Java / Spring Boot)

The API the mobile app talks to. Owns the persona catalog and location
directory, and calls the Python weather-data service for live weather
numbers + persona insights.

## Run locally

Requires Java 17+ and Maven.

```bash
# 1. start the Python weather-data service first (port 8000)
cd ../mausam-python-service
uvicorn main:app --reload --port 8000

# 2. in another terminal, start this API (port 8080)
cd mausam-java-api
mvn spring-boot:run
```

## Endpoints (called by the mobile app)

- `GET /api/personas` — the 8 persona definitions (id, label, icon, colors)
- `GET /api/locations?q=mum` — searchable city list
- `GET /api/home?city=Mumbai&persona=health` — **the main call**: current
  weather, hourly forecast, and persona-specific stats/insight, aggregated
  from the Python service
- `POST /api/auth/signup` / `POST /api/auth/login` — email/password auth,
  returns a JWT. `/api/home` requires this token (`Authorization: Bearer <token>`).

## User accounts

Stored in an embedded **H2 database**, file-based (not in-memory) —
accounts persist across server restarts, saved to `mausamdb.mv.db` in
whichever folder you run the server from. **Don't commit this file to
git** (add `*.mv.db` to `.gitignore`) — it contains real (hashed)
passwords once anyone signs up.

Inspect it directly while the server is running at
`http://localhost:8080/h2-console`:
- JDBC URL: `jdbc:h2:file:./mausamdb`
- Username: `sa`, password: blank

## Config

`src/main/resources/application.yml`:

```yaml
mausam:
  python-service:
    base-url: http://localhost:8000
```

Point this at wherever the Python service actually runs (e.g. its
container hostname in production).

## Notes

- If the Python service is unreachable, `/api/home` returns `502` with a
  clear `weather_service_unavailable` error body instead of a stack trace.
  If Python *is* reachable but couldn't get live weather (e.g. Open-Meteo
  down), that specific reason is forwarded instead of a generic message.
- Persona and location data are in-memory (`PersonaCatalog`,
  `LocationDirectory`) — swap for a database later without touching the
  controllers.
- The JWT secret in `application.yml` is a dev placeholder — replace it
  with a real secret (environment variable, not committed) before
  deploying anywhere real.
- This project could not be compiled in this sandbox (no network to
  fetch Spring Boot/Maven dependencies) — code was written and reviewed
  carefully, but run `mvn compile` on your machine to confirm before
  relying on it.
