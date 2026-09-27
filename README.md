# Transit Accessibility Gap Mapping — Backend

FastAPI backend for computing public transit accessibility: nearest stops,
estimated arrival times, fare calculation, trip sessions, and family
notification.

## Features
- Current location & destination input (with reverse geocoding via Nominatim)
- Nearest bus stop / auto stand lookup with distance (OpenStreetMap Overpass API)
- Estimated next-arrival timing (headway-based simulation — no live GTFS feed
  is publicly available for this data source, so this is clearly labeled as
  an estimate, not live tracking)
- Fare calculation (SQLite-backed fare slabs, distance-based)
- Trip sessions (SQLite) — tracks a full trip: locations, selected stop,
  vehicle type, strategy, fare, ETA
- WhatsApp notification to a trusted family member (Twilio Sandbox)
- Arrival confirmation, closing the trip loop

## Known limitations
- Distance for fare calculation uses haversine (straight-line) × 1.3
  multiplier as a road-distance approximation, not live routing, to avoid
  dependency on a public OSRM server.
- Bus stop / auto-stand data depends on OpenStreetMap community tagging
  completeness — coverage varies significantly between cities (this
  variance is itself a relevant accessibility-gap finding).
- WhatsApp notification uses Twilio's Sandbox, which (since April 2025)
  requires messages to use Twilio's Content Template API (`ContentSid`)
  rather than free-form text outside an active session — a production
  deployment would use an approved WhatsApp Business template.
- Uses SQLAlchemy `create_all` for schema setup; a production version
  would use Alembic migrations.

## Tech stack
FastAPI, SQLAlchemy (SQLite), httpx, Twilio, OpenStreetMap (Overpass +
Nominatim)

## Setup
\`\`\`bash
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.example .env        # fill in your own Twilio credentials
uvicorn app.main:app --reload
\`\`\`
Then visit `http://localhost:8000/docs` for interactive API testing.

## API overview
- `POST /location/current`, `POST /location/destination`
- `POST /transit/nearest-stop`
- `POST /transit/arrival-time`
- `POST /transit/fare`
- `POST /trip/start`, `POST /trip/select`, `GET /trip/{trip_id}`
- `POST /trip/notify/{trip_id}`, `POST /trip/confirm-arrival/{trip_id}`