from sqlalchemy.orm import Session
from app.database import FareSlab
from app.utils.haversine import haversine_distance_km

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