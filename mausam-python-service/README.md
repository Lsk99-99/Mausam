# Mausam Weather-Data Service (Python / FastAPI)

Internal service that owns raw weather conditions and turns them into
persona-specific stats + a one-line insight. Not called by the mobile
app directly — the Java main API calls this and re-exposes a clean
response.

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Performance & reliability

A single `/api/home` request from the frontend triggers three separate
calls into this service (current weather, hourly, persona metrics).
Without the fixes below, that meant the same Open-Meteo data got
fetched 2-3x over for one screen load.

- **Caching**: forecast/air-quality/marine responses are cached for 90
  seconds, keyed by rounded coordinates (`app/open_meteo.py`). In
  practice this collapses ~9 external calls per full page load down to
  ~3 — only the first of the three Java→Python calls does real work,
  the other two reuse its result. Verified directly: see the test in
  this project's development history: 3 calls total for one full
  current+hourly+persona cycle, down from 9.
- **Only successes are cached** — a failed fetch is never remembered,
  so the very next call retries for real rather than replaying the
  same failure for 90 seconds.
- **One automatic retry**: every Open-Meteo call retries once (with a
  short pause) before giving up. This network has shown intermittent
  connection blips reaching Open-Meteo — a quick retry turns a
  meaningful fraction of those into successes instead of an immediate
  failure.
- Geocoding results are cached indefinitely per city name (place
  names/coordinates don't change).

## Endpoints

- `GET /health` — service check
- `GET /weather/current?city=Mumbai&lat=&lon=` — temp, feels-like, condition, humidity, wind
- `GET /weather/hourly?city=Mumbai&hours=6&lat=&lon=` — next N hourly points
- `GET /weather/persona/{persona_id}?city=Mumbai&lat=&lon=` — persona stat cards + insight
  (add `condition=` for persona=health, or `activity=` for persona=fitness)
- `GET /locations/search?q=&limit=` — global city/town/village search via Open-Meteo's geocoder

Valid `persona_id` values: `health`, `fitness`, `beach`, `travel`, `family`, `farm`, `commute`, `events`

Passing `lat`/`lon` (when already known from a search result) skips
re-geocoding by name entirely — more reliable for villages/small towns,
which are more prone to name collisions than major cities.

## Notes

- **No mock/simulated data, ever.** If live data genuinely can't be
  fetched, endpoints return a `503` with a clear message instead of
  substituting a plausible-looking fake number — same honesty standard
  as Google Weather. Fields with no live source at all (tide times,
  flight-status alerts, pollen outside Europe) show `"Not available"`
  rather than a simulated value.
- **Live data**: current conditions, hourly forecast, AQI, UV index,
  humidity, wind, pressure, sunrise/sunset, visibility, soil moisture,
  and rain probability come from [Open-Meteo](https://open-meteo.com)
  (no API key needed) — see `app/open_meteo.py`.
- **Marine data** (wave height, water temp) is live for coastal
  coordinates via Open-Meteo's Marine API. For inland coordinates, the
  API correctly reports no data — the app shows this honestly rather
  than guessing.
- Persona logic lives in `app/insights.py` as plain, readable threshold
  rules — easy to tune without touching the API layer. Health and
  Fitness personas support sub-options (`condition`/`activity`) with
  guidance grounded in published thresholds (EPA AQI, WHO UV Index, NWS
  heat index, NOAA lightning safety) — see the module docstring for the
  full disclaimer text shown alongside them.
