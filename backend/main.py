from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import CORS_ORIGINS
from app.database import get_db
from app.routers import auth, market, ws

app = FastAPI(title="Vantra API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # must be explicit origins (not "*") when credentials are allowed
    allow_credentials=True,  # lets the browser send/receive the refresh-token cookie
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(market.router)
app.include_router(ws.router)


@app.get("/")
def read_root():
    return {"message": "Vantra backend is running"}


@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    """Reports whether the API is up AND can reach the database."""
    try:
        db.execute(text("select 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok", "service": "vantra-backend", "database": "ok"}
