"""WaysAhead - Transit Accessibility Gap Mapping API (all modules merged into one file)."""

import hashlib
import uuid
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from typing import Optional

import httpx
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, Float, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from pydantic import BaseModel, Field
from twilio.rest import Client
from fastapi import APIRouter, HTTPException, Depends, FastAPI


# ======================================================================
# Configuration  (from config.py)
# ======================================================================

load_dotenv()

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSRM_URL = "https://router.project-osrm.org"

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")

FARE_SLABS = [
    {"max_km": 2, "fare": 10},
    {"max_km": 5, "fare": 15},
    {"max_km": 10, "fare": 20},
    {"max_km": float("inf"), "fare_per_km_after_10": 2},
]
# Average headway (minutes between vehicles) - used for ESTIMATED arrival only,
# since no public live GTFS feed is available for our data source.
HEADWAY_MINUTES = {
    "bus_stop": (8, 20),     # typical city bus gap: 8-20 min
    "auto_stand": (2, 7),    # autos/shared autos: more frequent, shorter wait
}


# ======================================================================
# Database & models  (from database.py)
# ======================================================================

DATABASE_URL = "sqlite:///./transit_app.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class FareSlab(Base):
    __tablename__ = "fare_slabs"

    id = Column(Integer, primary_key=True, index=True)
    max_km = Column(Float, nullable=False)       # upper distance bound for this slab
    fare = Column(Float, nullable=False)          # flat fare if within this slab
    vehicle_type = Column(String, default="bus")  # "bus" or "auto" - different rates


def init_db():
    Base.metadata.create_all(bind=engine)


def seed_fare_slabs():
    db = SessionLocal()
    existing = db.query(FareSlab).count()
    if existing == 0:
        default_slabs = [
            FareSlab(max_km=2, fare=10, vehicle_type="bus"),
            FareSlab(max_km=5, fare=15, vehicle_type="bus"),
            FareSlab(max_km=10, fare=20, vehicle_type="bus"),
            FareSlab(max_km=999, fare=30, vehicle_type="bus"),
            FareSlab(max_km=2, fare=25, vehicle_type="auto"),
            FareSlab(max_km=5, fare=45, vehicle_type="auto"),
            FareSlab(max_km=10, fare=80, vehicle_type="auto"),
            FareSlab(max_km=999, fare=120, vehicle_type="auto"),
        ]
        db.add_all(default_slabs)
        db.commit()
    db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))

    current_lat = Column(Float, nullable=False)
    current_lon = Column(Float, nullable=False)
    dest_lat = Column(Float, nullable=False)
    dest_lon = Column(Float, nullable=False)

    selected_stop_name = Column(String, nullable=True)
    selected_stop_lat = Column(Float, nullable=True)
    selected_stop_lon = Column(Float, nullable=True)
    selected_stop_type = Column(String, nullable=True)

    vehicle_type = Column(String, nullable=True)   # "bus" or "auto"
    strategy = Column(String, nullable=True)        # "nearest" / "cheapest" / "fastest"

    fare = Column(Float, nullable=True)
    estimated_wait_minutes = Column(Integer, nullable=True)

    status = Column(String, default="started")  # started -> selected -> notified -> completed
    created_at = Column(String, default=lambda: datetime.now().isoformat())
    family_contact = Column(String, nullable=True)  # WhatsApp number, e.g. "+919876543210"


# ======================================================================
# Pydantic schemas  (from schemas.py)
# ======================================================================

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


# ======================================================================
# Haversine utility  (from haversine.py)
# ======================================================================

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance between two lat/lon points, in kilometers.
    Uses the haversine formula.
    """
    R = 6371.0  # Earth's radius in km

    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)

    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return round(R * c, 3)


# ======================================================================
# Geo service  (from geo_service.py)
# ======================================================================

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


# ======================================================================
# Arrival service  (from arrival_service.py)
# ======================================================================

def estimate_next_arrival(stop_lat: float, stop_lon: float, stop_type: str) -> dict:
    """
    Estimate next vehicle arrival at a stop using an average-headway model.
    NOT live data - no GPS/GTFS-realtime feed is used. This is a deterministic
    pseudo-random estimate seeded by location + current 10-minute time bucket,
    so it's stable for a few minutes but varies across stops.
    """
    low, high = HEADWAY_MINUTES.get(stop_type, (10, 15))

    # Seed so the same stop gives a consistent estimate within the same time window
    time_bucket = datetime.now().strftime("%Y%m%d%H") + str(datetime.now().minute // 10)
    seed_str = f"{stop_lat:.5f},{stop_lon:.5f},{time_bucket}"
    seed_int = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)

    wait_minutes = low + (seed_int % (high - low + 1))
    eta_time = datetime.now() + timedelta(minutes=wait_minutes)

    return {
        "estimated_wait_minutes": wait_minutes,
        "estimated_arrival_time": eta_time.strftime("%H:%M"),
        "basis": f"Estimated from average headway ({low}-{high} min) for {stop_type.replace('_', ' ')}, not live tracking",
        "is_live_data": False
    }


# ======================================================================
# Fare service  (from fare_service.py)
# ======================================================================

ROAD_DISTANCE_MULTIPLIER = 1.3  # approximates road winding vs straight-line


def calculate_fare(db: Session, origin_lat, origin_lon, dest_lat, dest_lon, vehicle_type: str = "bus") -> dict:
    straight_km = haversine_distance_km(origin_lat, origin_lon, dest_lat, dest_lon)
    approx_road_km = round(straight_km * ROAD_DISTANCE_MULTIPLIER, 2)

    slab = (
        db.query(FareSlab)
        .filter(FareSlab.vehicle_type == vehicle_type, FareSlab.max_km >= approx_road_km)
        .order_by(FareSlab.max_km.asc())
        .first()
    )

    if not slab:
        return {
            "error": f"No fare slab found for {approx_road_km} km, vehicle_type={vehicle_type}"
        }

    return {
        "straight_line_km": straight_km,
        "approx_road_km": approx_road_km,
        "vehicle_type": vehicle_type,
        "fare": slab.fare,
        "note": "Distance approximated from straight-line coordinates (no live routing API used)"
    }


# ======================================================================
# Notification service  (from notify_service.py)
# ======================================================================

def send_whatsapp_notification(to_number: str, message: str) -> dict:
    """
    Sends a WhatsApp message via Twilio Sandbox.
    to_number must be in E.164 format, e.g. "+919876543210".
    Both sender (sandbox) and receiver must have completed the Twilio
    'join <code>' sandbox step for this to succeed.
    """
    if not TWILIO_SID or not TWILIO_AUTH_TOKEN or not TWILIO_WHATSAPP_FROM:
        return {"success": False, "error": "Twilio credentials not configured in .env"}

    try:
        client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{to_number}",
            body=message
        )
        return {"success": True, "sid": msg.sid, "status": msg.status}
    except Exception as e:
        return {"success": False, "error": str(e)}


def build_trip_message(trip) -> str:
    """Compose a readable trip-summary message for the family member."""
    return (
        f"🚏 Trip Update\n"
        f"Traveler is heading to destination via {trip.selected_stop_name} "
        f"({trip.selected_stop_type.replace('_', ' ')}).\n"
        f"Vehicle: {trip.vehicle_type}\n"
        f"Fare: ₹{trip.fare}\n"
        f"Estimated wait: {trip.estimated_wait_minutes} min\n"
        f"Trip ID: {trip.trip_id}"
    )


# ======================================================================
# Trip service  (from trip_service.py)
# ======================================================================

def create_trip(db: Session, current_lat, current_lon, dest_lat, dest_lon) -> Trip:
    trip = Trip(
        current_lat=current_lat,
        current_lon=current_lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        status="started"
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def select_trip_options(db: Session, selection) -> Trip:
    trip = db.query(Trip).filter(Trip.trip_id == selection.trip_id).first()
    if not trip:
        return None

    # Fare: based on current -> destination distance, using chosen vehicle type
    fare_result = calculate_fare(
        db, trip.current_lat, trip.current_lon, trip.dest_lat, trip.dest_lon,
        selection.vehicle_type
    )

    # Arrival: based on the specific stop the user picked
    arrival_result = estimate_next_arrival(
        selection.stop_lat, selection.stop_lon, selection.stop_type
    )

    trip.selected_stop_name = selection.stop_name
    trip.selected_stop_lat = selection.stop_lat
    trip.selected_stop_lon = selection.stop_lon
    trip.selected_stop_type = selection.stop_type
    trip.vehicle_type = selection.vehicle_type
    trip.strategy = selection.strategy
    trip.fare = fare_result.get("fare")
    trip.estimated_wait_minutes = arrival_result.get("estimated_wait_minutes")
    trip.status = "selected"
    trip.family_contact = selection.family_contact

    db.commit()
    db.refresh(trip)
    return trip


def get_trip(db: Session, trip_id: str) -> Trip:
    return db.query(Trip).filter(Trip.trip_id == trip_id).first()


# ======================================================================
# Routes: /location  (from location.py)
# ======================================================================

location_router = APIRouter()

@location_router.post("/current")
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

@location_router.post("/destination")
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


# ======================================================================
# Routes: /transit  (from transit.py)
# ======================================================================

transit_router = APIRouter()


@transit_router.post("/nearest-stop")
async def nearest_stop(location: Location, limit: int = 5):
    try:
        stops = await find_nearby_stops(location.lat, location.lon)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch stop data from OSM: {str(e)}")

    if not stops:
        return {"message": "No bus stops or auto stands found nearby", "stops": []}

    ranked = rank_stops_by_distance(location.lat, location.lon, stops)
    return {"stops": ranked[:limit]}


@transit_router.post("/arrival-time")
def arrival_time(stop: StopInput):
    result = estimate_next_arrival(stop.lat, stop.lon, stop.type)
    return {
        "stop_name": stop.name,
        "stop_type": stop.type,
        **result
    }


@transit_router.post("/fare")
def fare(locations: LocationPair, vehicle_type: str = "bus", db: Session = Depends(get_db)):
    result = calculate_fare(
        db,
        locations.current.lat, locations.current.lon,
        locations.destination.lat, locations.destination.lon,
        vehicle_type
    )
    return result


# ======================================================================
# Routes: /trip  (from trip.py)
# ======================================================================

trip_router = APIRouter()


@trip_router.post("/start")
def start_trip(payload: TripStart, db: Session = Depends(get_db)):
    trip = create_trip(
        db,
        payload.current.lat, payload.current.lon,
        payload.destination.lat, payload.destination.lon
    )
    return {"trip_id": trip.trip_id, "status": trip.status}


@trip_router.post("/select")
def select_trip(selection: TripSelection, db: Session = Depends(get_db)):
    trip = select_trip_options(db, selection)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    return {
        "trip_id": trip.trip_id,
        "selected_stop": trip.selected_stop_name,
        "vehicle_type": trip.vehicle_type,
        "strategy": trip.strategy,
        "fare": trip.fare,
        "estimated_wait_minutes": trip.estimated_wait_minutes,
        "status": trip.status
    }


@trip_router.get("/{trip_id}")
def view_trip(trip_id: str, db: Session = Depends(get_db)):
    trip = get_trip(db, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip.__dict__

@trip_router.post("/notify/{trip_id}")
def notify_family(trip_id: str, db: Session = Depends(get_db)):
    trip = get_trip(db, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if not trip.family_contact:
        raise HTTPException(status_code=400, detail="No family contact saved for this trip")

    message = build_trip_message(trip)
    result = send_whatsapp_notification(trip.family_contact, message)

    if result["success"]:
        trip.status = "notified"
        db.commit()

    return result


@trip_router.post("/confirm-arrival/{trip_id}")
def confirm_arrival(trip_id: str, db: Session = Depends(get_db)):
    trip = get_trip(db, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    trip.status = "completed"
    db.commit()

    # Optionally notify family that user arrived safely
    if trip.family_contact:
        arrival_msg = f"✅ Traveler has arrived safely at their destination.\nTrip ID: {trip.trip_id}"
        send_whatsapp_notification(trip.family_contact, arrival_msg)

    return {
        "trip_id": trip.trip_id,
        "status": trip.status,
        "message": "Arrival confirmed"
    }


# ======================================================================
# App entrypoint  (from main.py)
# ======================================================================

app = FastAPI(title="Transit Accessibility Gap Mapping API")

@app.on_event("startup")
def startup():
    init_db()
    seed_fare_slabs()

app.include_router(location_router, prefix="/location", tags=["Location"])
app.include_router(transit_router, prefix="/transit", tags=["Transit"])
app.include_router(trip_router, prefix="/trip", tags=["Trip"])

@app.get("/")
def health():
    return {"status": "ok"}
