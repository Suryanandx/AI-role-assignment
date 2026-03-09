"""Strawberry GraphQL schema: Job, CreateJobInput, Query, Mutation."""

import uuid
from enum import Enum

import strawberry

from app.models import Job as PydanticJob


@strawberry.enum
class JobStatus(Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


@strawberry.type
class SERPResultType:
    rank: int
    url: str
    title: str
    snippet: str


@strawberry.type
class SERPAnalysisType:
    themes: list[str]
    subtopics: list[str]
    paa_questions: list[str]
    keyword_candidates: list[str]


@strawberry.type
class OutlineSectionType:
    heading_level: int
    title: str
    bullet_points: list[str]


@strawberry.type
class OutlineType:
    sections: list[OutlineSectionType]


@strawberry.type
class ArticleSectionType:
    level: int
    heading: str
    content: str


@strawberry.type
class ArticleType:
    sections: list[ArticleSectionType]


@strawberry.type
class SEOMetadataType:
    title_tag: str
    meta_description: str
    primary_keyword: str
    secondary_keywords: list[str]


@strawberry.type
class InternalLinkType:
    anchor_text: str
    target_topic: str


@strawberry.type
class ExternalRefType:
    url: str
    title: str
    placement_context: str


@strawberry.type
class FAQItemType:
    question: str
    answer: str


@strawberry.type
class JobType:
    id: strawberry.ID
    status: JobStatus
    topic: str
    word_count: int
    language: str
    serp_raw: list[SERPResultType] | None
    serp_analysis: SERPAnalysisType | None
    outline: OutlineType | None
    article: ArticleType | None
    metadata: SEOMetadataType | None
    internal_links: list[InternalLinkType]
    external_refs: list[ExternalRefType]
    quality_score: float | None
    faq: list[FAQItemType] | None
    error: str | None
    created_at: str
    updated_at: str


@strawberry.input(name="CreateJobInput")
class CreateJobInputType:
    topic: str
    word_count: int = 1500
    language: str = "en"


def _job_to_gql(job: PydanticJob) -> JobType:
    serp_raw = None
    if job.serp_raw:
        serp_raw = [
            SERPResultType(rank=r.rank, url=r.url, title=r.title, snippet=r.snippet)
            for r in job.serp_raw
        ]
    serp_analysis = None
    if job.serp_analysis:
        a = job.serp_analysis
        serp_analysis = SERPAnalysisType(
            themes=a.themes,
            subtopics=a.subtopics,
            paa_questions=a.paa_questions,
            keyword_candidates=a.keyword_candidates,
        )
    outline = None
    if job.outline:
        outline = OutlineType(
            sections=[
                OutlineSectionType(
                    heading_level=s.heading_level,
                    title=s.title,
                    bullet_points=s.bullet_points or [],
                )
                for s in job.outline.sections
            ]
        )
    article = None
    if job.article:
        article = ArticleType(
            sections=[
                ArticleSectionType(level=s.level, heading=s.heading, content=s.content)
                for s in job.article.sections
            ]
        )
    metadata = None
    if job.metadata:
        m = job.metadata
        metadata = SEOMetadataType(
            title_tag=m.title_tag,
            meta_description=m.meta_description,
            primary_keyword=m.primary_keyword,
            secondary_keywords=m.secondary_keywords or [],
        )
    internal_links = [
        InternalLinkType(anchor_text=l.anchor_text, target_topic=l.target_topic)
        for l in (job.internal_links or [])
    ]
    external_refs = [
        ExternalRefType(url=r.url, title=r.title, placement_context=r.placement_context)
        for r in (job.external_refs or [])
    ]
    faq = None
    if job.faq:
        faq = [FAQItemType(question=f.question, answer=f.answer) for f in job.faq]
    created_at = job.created_at.isoformat() if job.created_at else ""
    updated_at = job.updated_at.isoformat() if job.updated_at else ""
    return JobType(
        id=strawberry.ID(str(job.id)),
        status=JobStatus[job.status.name],
        topic=job.topic,
        word_count=job.word_count,
        language=job.language,
        serp_raw=serp_raw,
        serp_analysis=serp_analysis,
        outline=outline,
        article=article,
        metadata=metadata,
        internal_links=internal_links,
        external_refs=external_refs,
        quality_score=job.quality_score,
        faq=faq,
        error=job.error,
        created_at=created_at,
        updated_at=updated_at,
    )


@strawberry.type
class Query:
    @strawberry.field
    def job(self, id: strawberry.ID, info: strawberry.Info) -> JobType | None:
        from app.db import get_job

        try:
            job_id = uuid.UUID(str(id))
        except ValueError:
            return None
        ctx = info.context
        job = get_job(ctx["db_path"], job_id)
        if job is None:
            return None
        return _job_to_gql(job)


@strawberry.type
class Mutation:
    @strawberry.mutation(name="createJob")
    def create_job(self, input: CreateJobInputType, info: strawberry.Info) -> strawberry.ID:
        from app.models import CreateJobInput

        from app.pipeline import create_job_step

        ctx = info.context
        pydantic_input = CreateJobInput(
            topic=input.topic,
            word_count=input.word_count,
            language=input.language,
        )
        job_id = create_job_step(pydantic_input, ctx["db_path"])
        return strawberry.ID(str(job_id))

    @strawberry.mutation(name="runPipeline")
    def run_pipeline(self, job_id: strawberry.ID, info: strawberry.Info) -> JobType | None:
        from app.pipeline import run_pipeline

        try:
            uid = uuid.UUID(str(job_id))
        except ValueError:
            return None
        ctx = info.context
        job = run_pipeline(
            uid,
            ctx["db_path"],
            ctx["serp_client"],
            ctx["llm_client"],
        )
        if job is None:
            return None
        return _job_to_gql(job)


schema = strawberry.Schema(query=Query, mutation=Mutation)
