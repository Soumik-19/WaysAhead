from fastapi import FastAPI
from app.routers import location, transit, trip

app = FastAPI(title="Transit Accessibility Gap Mapping API")

app.include_router(location.router, prefix="/location", tags=["Location"])
app.include_router(transit.router, prefix="/transit", tags=["Transit"])
app.include_router(trip.router, prefix="/trip", tags=["Trip"])

@app.get("/")
def health():
    return {"status": "ok"}
from fastapi import FastAPI
from app.routers import location, transit, trip
from app.database import init_db, seed_fare_slabs

app = FastAPI(title="Transit Accessibility Gap Mapping API")

@app.on_event("startup")
def startup():
    init_db()
    seed_fare_slabs()

app.include_router(location.router, prefix="/location", tags=["Location"])
app.include_router(transit.router, prefix="/transit", tags=["Transit"])
app.include_router(trip.router, prefix="/trip", tags=["Trip"])

@app.get("/")
def health():
    return {"status": "ok"}