from sqlalchemy.orm import Session
from app.database import Trip
from app.services.fare_service import calculate_fare
from app.services.arrival_service import estimate_next_arrival


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