from typing import List, Optional
from pydantic import BaseModel


class CurrentWeather(BaseModel):
    city: str
    temp_c: float
    feels_like_c: float
    condition: str
    humidity_pct: Optional[int] = None
    wind_kmh: Optional[float] = None
    is_live: bool = True


class HourlyPoint(BaseModel):
    label: str
    temp_c: float
    condition: str


class HourlyForecast(BaseModel):
    city: str
    hours: List[HourlyPoint]


class StatItem(BaseModel):
    icon: str
    label: str
    value: str
    caption: Optional[str] = ""


class PersonaMetrics(BaseModel):
    persona_id: str
    city: str
    stats: List[StatItem]
    insight: str
    is_live: bool = True
    disclaimer: Optional[str] = None
