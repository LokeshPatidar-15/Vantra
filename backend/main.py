from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.routers import auth

app = FastAPI(title="Vantra API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)


@app.get("/")
def read_root():
    return {"message": "Vantra backend is running"}


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "vantra-backend"}
