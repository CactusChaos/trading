from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.database import engine, Base
from app.routers import projects, attempts, comments, markets, cache

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="Polymarket Backtester", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(attempts.router, prefix="/api", tags=["attempts"])
app.include_router(comments.router, prefix="/api", tags=["comments"])
app.include_router(markets.router, prefix="/api/markets", tags=["markets"])
app.include_router(cache.router, prefix="/api/cache", tags=["cache"])

# Templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory=templates_dir)

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")
