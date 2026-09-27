from sqlalchemy import create_engine, Column, Integer, Float, String
from sqlalchemy.orm import sessionmaker, declarative_base

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
import uuid
from datetime import datetime

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