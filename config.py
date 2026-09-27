import os
from dotenv import load_dotenv

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