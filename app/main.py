from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.config import get_settings
from app.routers import hotels, rates, users, reports, integrations, zatca, pms, billing, ml

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="AI-Powered Hotel Revenue Management System for Saudi Arabia",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(hotels.router, prefix="/api/v1/hotels", tags=["Hotels"])
app.include_router(rates.router, prefix="/api/v1/rates", tags=["Rates"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["Integrations"])
app.include_router(zatca.router, prefix="/api/v1/zatca", tags=["ZATCA"])
app.include_router(pms.router, prefix="/api/v1/pms", tags=["PMS"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["Billing"])
app.include_router(ml.router, prefix="/api/v1/ml", tags=["ML"])


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "0.1.0", "environment": settings.environment}
