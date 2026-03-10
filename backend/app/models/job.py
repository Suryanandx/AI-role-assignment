import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from app.models.article import Article
from app.models.faq import FAQItem
from app.models.links import ExternalRef, InternalLink
from app.models.metadata import SEOMetadata
from app.models.outline import Outline
from app.models.serp import SERPAnalysis, SERPResult


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class CreateJobInput(BaseModel):
    topic: str
    word_count: int = 1500
    language: str = "en"


class Job(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    status: JobStatus
    topic: str
    word_count: int
    language: str
    current_step: str | None = None
    serp_raw: list[SERPResult] | None = None
    serp_analysis: SERPAnalysis | None = None
    outline: Outline | None = None
    article: Article | None = None
    metadata: SEOMetadata | None = None
    internal_links: list[InternalLink] = []
    external_refs: list[ExternalRef] = []
    quality_score: float | None = None
    faq: list[FAQItem] | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
