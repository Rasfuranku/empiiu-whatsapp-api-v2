from fastapi import FastAPI
from app.api.v1.endpoints import router as router_v1
from app.api.v2.endpoints import router as router_v2
from app.db.session import engine
from app.db.models import Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Empiiu Onboarding Agent")

@app.on_event("startup")
async def startup_event():
    # We keep this for dev convenience, but in prod we rely on Alembic
    logger.info("Initializing database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.include_router(router_v1, prefix="/api/v1")
app.include_router(router_v2, prefix="/api/v2")

@app.get("/")
async def root():
    return {"message": "Empiiu Onboarding System Running", "versions": ["v1", "v2"]}