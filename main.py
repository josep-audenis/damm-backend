import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from routers import catalog, data, db, jobs, optimize
from services.database import db_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


app = FastAPI(
    title="Damm Smart Truck API",
    version="0.1.0",
    description="Schema-first API scaffold for route and load optimization.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db_service.init_db()

app.include_router(catalog.router)
app.include_router(data.router)
app.include_router(db.router)
app.include_router(jobs.router)
app.include_router(optimize.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> RedirectResponse:
    # Land on Swagger so anyone hitting the bare host sees the API surface.
    # The static "DB Manager" demo at /app/ was retired in favour of the
    # React frontend that lives in the damm-frontend repo.
    return RedirectResponse(url="/docs")
