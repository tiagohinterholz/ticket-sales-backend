import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.bookings import router as bookings_router
from app.api.v1.events import router as events_router
from app.api.v1.gate import router as gate_router
from app.api.v1.organizer import router as organizer_router
from app.api.v1.payments import router as payments_router
from app.api.v1.tickets import router as tickets_router
from app.api.v1.transfers import router as transfers_router
from app.db.session import SessionLocal
from app.services.booking import sweep_expired_holds

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _run_sweep_expired_holds() -> None:
    db = SessionLocal()
    try:
        released_count = sweep_expired_holds(db)
        logger.info("sweep_expired_holds released %s seat(s)", released_count)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()
    scheduler.add_job(_run_sweep_expired_holds, "interval", seconds=60)
    scheduler.start()
    logger.info("seat hold expiry sweep scheduler started")
    try:
        yield
    finally:
        scheduler.shutdown()


app = FastAPI(title="Ticket Sales Platform API", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(events_router)
app.include_router(bookings_router)
app.include_router(payments_router)
app.include_router(tickets_router)
app.include_router(gate_router)
app.include_router(transfers_router)
app.include_router(organizer_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
