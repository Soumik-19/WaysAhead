from fastapi import APIRouter, HTTPException
from app.models.schemas import Location
from app.services.geo_service import reverse_geocode

router = APIRouter()

@router.post("/current")
async def set_current_location(location: Location):
    try:
        address = await reverse_geocode(location.lat, location.lon)
    except Exception:
        address = "Unable to resolve address"
    return {
        "lat": location.lat,
        "lon": location.lon,
        "address": address
    }

@router.post("/destination")
async def set_destination_location(location: Location):
    try:
        address = await reverse_geocode(location.lat, location.lon)
    except Exception:
        address = "Unable to resolve address"
    return {
        "lat": location.lat,
        "lon": location.lon,
        "address": address
    }