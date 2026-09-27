import httpx
from app.config import OVERPASS_URL
from app.utils.haversine import haversine_distance_km

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


async def reverse_geocode(lat: float, lon: float) -> str:
    """Convert coordinates into a human-readable address string."""
    params = {"lat": lat, "lon": lon, "format": "json"}
    headers = {"User-Agent": "transit-access-app"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(NOMINATIM_URL, params=params, headers=headers, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("display_name", "Unknown location")


async def find_nearby_stops(lat: float, lon: float, radius_m: int = 1500) -> list[dict]:
    """Query Overpass API for bus stops and auto/taxi stands within radius_m meters."""
    query = f"""
    [out:json][timeout:25];
    (
      node["highway"="bus_stop"](around:{radius_m},{lat},{lon});
      node["amenity"="taxi"](around:{radius_m},{lat},{lon});
    );
    out body;
    """
    headers = {
        "Accept": "*/*",
        "User-Agent": "transit-access-app"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(OVERPASS_URL, data={"data": query}, headers=headers, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()

    stops = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        stops.append({
            "name": tags.get("name", "Unnamed stop"),
            "lat": element["lat"],
            "lon": element["lon"],
            "type": "bus_stop" if tags.get("highway") == "bus_stop" else "auto_stand"
        })
    return stops


def rank_stops_by_distance(user_lat: float, user_lon: float, stops: list[dict]) -> list[dict]:
    """Attach distance_km to each stop and sort nearest-first."""
    for stop in stops:
        stop["distance_km"] = haversine_distance_km(user_lat, user_lon, stop["lat"], stop["lon"])
    return sorted(stops, key=lambda s: s["distance_km"])