from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.db import init_db

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(settings.db_path)
    yield


app = FastAPI(title="SEO Article Generator", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}
