from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Vantra API")

# Allow the frontend (running on a different port) to call this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Vantra backend is running"}

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "vantra-backend"}
