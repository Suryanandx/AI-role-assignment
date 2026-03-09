"""GraphQL context: db_path and clients for resolvers."""

from app.config import Settings
from app.services import get_llm_client, get_serp_client


def get_context():
    settings = Settings()
    return {
        "db_path": settings.db_path,
        "serp_client": get_serp_client(settings.serp_use_mock, settings),
        "llm_client": get_llm_client(settings),
    }
