import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import appointments, auth, patients, treatments
from app.api.v1 import ai_workflows, agent_swarm, claims_clearinghouse, ecah_engine, fleet_sync, license_reviews, telephony_mesh, agents, clinical
from app.core.database import Base, engine, ensure_multitenant_schema
from app.models import models

Base.metadata.create_all(bind=engine)
ensure_multitenant_schema()

app = FastAPI(
    title="GFI Dental OS API",
    version="1.0.0",
    description="Clinic-scoped dental practice operations and AI workflows.",
)

# Automatically handle CORS for local dev and cloud deployments (Vercel/Render)
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://192.168.31.153:3000",
]
if os.environ.get("PRODUCTION_DOMAIN"):
    ALLOWED_ORIGINS.append(os.environ.get("PRODUCTION_DOMAIN"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In a real strict production app, use ALLOWED_ORIGINS. We use * for seamless demo deployment.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Admin-Bypass-Key", "Idempotency-Key"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(patients.router, prefix="/api/v1", tags=["Patients"])
app.include_router(appointments.router, prefix="/api/v1", tags=["Appointments"])
app.include_router(treatments.router, prefix="/api/v1/treatments", tags=["Treatment Plans"])
app.include_router(ai_workflows.router, prefix="/api/v1")
app.include_router(ecah_engine.router)
app.include_router(claims_clearinghouse.router)
app.include_router(license_reviews.router)
app.include_router(fleet_sync.router)
app.include_router(agent_swarm.router)
app.include_router(telephony_mesh.router)
app.include_router(agents.router, prefix="/api/v1")
app.include_router(clinical.router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def read_root():
    return {"status": "ok", "service": "GFI Dental OS API"}