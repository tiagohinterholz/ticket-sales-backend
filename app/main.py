from fastapi import FastAPI

from app.api.v1.auth import router as auth_router

app = FastAPI(title="Ticket Sales Platform API")

app.include_router(auth_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
