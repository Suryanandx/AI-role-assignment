from contextlib import asynccontextmanager

from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from app.api.context import get_context as build_graphql_context
from app.api.schema import schema
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


async def get_context():
    return build_graphql_context()


graphql_app = GraphQLRouter(schema, context_getter=get_context)
app.include_router(graphql_app, prefix="/graphql")
