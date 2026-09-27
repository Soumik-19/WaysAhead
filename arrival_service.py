import hashlib
from datetime import datetime, timedelta
from app.config import HEADWAY_MINUTES


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