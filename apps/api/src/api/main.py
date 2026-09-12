from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import ingest, nodes, verification, water_surface, work_orders

app = FastAPI(title="Floodtir API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(nodes.router)
app.include_router(water_surface.router)
app.include_router(work_orders.router)
app.include_router(verification.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
