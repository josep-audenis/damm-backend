from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from routers import catalog, data, db, optimize
from services.database import db_service


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
app.include_router(optimize.router)
app.mount("/app", StaticFiles(directory="static", html=True), name="app")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/app/")
