from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.routers import (
    api_keys,
    appointments,
    auth,
    departments,
    doctors,
    public,
    schedules,
    superadmin,
    users,
)

# Import models so they're registered on Base.metadata before create_all()
from app import models  # noqa: F401


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # For local/dev use. For production, prefer proper migrations (e.g. Alembic).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="REST API for a medical clinic appointment booking portal.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}


app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
app.include_router(departments.router, prefix=settings.API_V1_PREFIX)
app.include_router(doctors.router, prefix=settings.API_V1_PREFIX)
app.include_router(schedules.router, prefix=settings.API_V1_PREFIX)
app.include_router(appointments.router, prefix=settings.API_V1_PREFIX)
app.include_router(api_keys.router, prefix=settings.API_V1_PREFIX)
app.include_router(public.router, prefix=settings.API_V1_PREFIX)
app.include_router(superadmin.router, prefix=settings.API_V1_PREFIX)
