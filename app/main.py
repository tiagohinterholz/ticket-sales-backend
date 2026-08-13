from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.bookings import router as bookings_router
from app.api.v1.events import router as events_router

app = FastAPI(title="Ticket Sales Platform API")

app.include_router(auth_router)
app.include_router(events_router)
app.include_router(bookings_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
