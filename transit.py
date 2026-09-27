from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.models.schemas import Location, StopInput, LocationPair
from app.services.geo_service import find_nearby_stops, rank_stops_by_distance
from app.services.arrival_service import estimate_next_arrival
from app.services.fare_service import calculate_fare
from app.database import get_db

router = APIRouter()


@router.post("/nearest-stop")
async def nearest_stop(location: Location, limit: int = 5):
    try:
        stops = await find_nearby_stops(location.lat, location.lon)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch stop data from OSM: {str(e)}")

    if not stops:
        return {"message": "No bus stops or auto stands found nearby", "stops": []}

    ranked = rank_stops_by_distance(location.lat, location.lon, stops)
    return {"stops": ranked[:limit]}


@router.post("/arrival-time")
def arrival_time(stop: StopInput):
    result = estimate_next_arrival(stop.lat, stop.lon, stop.type)
    return {
        "stop_name": stop.name,
        "stop_type": stop.type,
        **result
    }


@router.post("/fare")
def fare(locations: LocationPair, vehicle_type: str = "bus", db: Session = Depends(get_db)):
    result = calculate_fare(
        db,
        locations.current.lat, locations.current.lon,
        locations.destination.lat, locations.destination.lon,
        vehicle_type
    )
    return result