from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import appointments, auth, patients, treatments
from app.api.v1 import ai_workflows, agent_swarm, claims_clearinghouse, ecah_engine, fleet_sync, license_reviews, telephony_mesh
from app.core.database import Base, engine, ensure_multitenant_schema
from app.models import models

ensure_multitenant_schema()
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="GFI Dental OS API",
    version="1.0.0",
    description="Clinic-scoped dental practice operations and AI workflows.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.31.153:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/", tags=["Health"])
def read_root():
    return {"status": "ok", "service": "GFI Dental OS API"}