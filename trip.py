from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.models.schemas import TripStart, TripSelection
from app.database import get_db
from app.services.trip_service import create_trip, select_trip_options, get_trip
from app.services.notify_service import send_whatsapp_notification, build_trip_message
from datetime import datetime

router = APIRouter()


@router.post("/start")
def start_trip(payload: TripStart, db: Session = Depends(get_db)):
    trip = create_trip(
        db,
        payload.current.lat, payload.current.lon,
        payload.destination.lat, payload.destination.lon
    )
    return {"trip_id": trip.trip_id, "status": trip.status}


@router.post("/select")
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


@router.get("/{trip_id}")
def view_trip(trip_id: str, db: Session = Depends(get_db)):
    trip = get_trip(db, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip.__dict__

@router.post("/notify/{trip_id}")
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


@router.post("/confirm-arrival/{trip_id}")
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