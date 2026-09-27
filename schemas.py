from pydantic import BaseModel, Field

class Location(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)

class LocationPair(BaseModel):
    current: Location
    destination: Location

class StopInput(BaseModel):
    name: str
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    type: str  # "bus_stop" or "auto_stand"

from typing import Optional

class TripStart(BaseModel):
    current: Location
    destination: Location


class TripSelection(BaseModel):
    trip_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    stop_type: str
    vehicle_type: str
    strategy: str
    family_contact: str   # new field, e.g. "+919876543210"