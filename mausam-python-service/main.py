from fastapi import FastAPI

from app.routers import weather

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port
    )

app = FastAPI(
    title="Mausam Weather-Data Service",
    description="Internal service: raw weather conditions + persona-specific insights. "
                "Called by the Java main API — not exposed directly to the mobile app.",
    version="0.1.0",
)

app.include_router(weather.router)
app.include_router(weather.location_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "mausam-weather-data"}

