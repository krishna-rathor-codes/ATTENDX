from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db import Base, engine
from app.routers import auth, student, teacher


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", description="Secure teacher attendance management API", lifespan=lifespan)
allowed_origins = {settings.frontend_origin, "http://127.0.0.1:5173", "http://localhost:5173"}
app.add_middleware(CORSMiddleware, allow_origins=sorted(allowed_origins), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix="/api")
app.include_router(teacher.router, prefix="/api")
app.include_router(student.router, prefix="/api")


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "attendx-api"}
