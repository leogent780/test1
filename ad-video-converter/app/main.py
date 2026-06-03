from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from app.routers import upload, pages
from app.config import DIRS

app = FastAPI(title="Ad Video Converter")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 & 업로드 파일 서빙
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(Path(__file__).parent.parent / "uploads")), name="uploads")

app.include_router(pages.router)
app.include_router(upload.router)
