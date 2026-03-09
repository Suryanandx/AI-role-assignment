import json
import re
import uuid

from pydantic import ValidationError

from app.db import create_job, get_job, update_job
from app.models import Article, CreateJobInput, Job, Outline, SERPAnalysis, SERPResult
from app.services.llm import GenerateOptions, LLMClient
from app.services.serp import SERPClient

_STOPWORDS = frozenset(
    {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
     "in", "is", "it", "of", "on", "or", "the", "to", "what", "when", "which",
     "with", "you"}
)


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _analyze_serp(results: list[SERPResult], topic: str) -> SERPAnalysis:
    if not results:
        return SERPAnalysis()

    all_tokens: list[str] = []
    for r in results:
        all_tokens.extend(_tokenize(r.title))
        all_tokens.extend(_tokenize(r.snippet))

    topic_tokens = _tokenize(topic)
    counts: dict[str, int] = {}
    for t in all_tokens:
        counts[t] = counts.get(t, 0) + 1
    themes = sorted(counts.keys(), key=lambda x: (-counts[x], x))[:10]
    if topic_tokens:
        for t in topic_tokens:
            if t not in themes:
                themes.insert(0, t)
        themes = themes[:10]

    subtopics = [r.title[:80].strip() for r in results[:5] if r.title]

    paa_questions: list[str] = []
    for r in results:
        s = (r.snippet or "").strip()
        if "?" in s or "how to" in s.lower() or "what is" in s.lower():
            q = s.split(".")[0].strip()
            if q and len(paa_questions) < 3:
                paa_questions.append(q[:120])

    keyword_candidates = list(dict.fromkeys(themes + topic_tokens))[:15]

    return SERPAnalysis(
        themes=themes,
        subtopics=subtopics,
        paa_questions=paa_questions,
        keyword_candidates=keyword_candidates,
    )


def create_job_step(input: CreateJobInput, db_path: str) -> uuid.UUID:
    job = create_job(db_path, input)
    return job.id


def run_serp_step(
    job_id: uuid.UUID,
    db_path: str,
    serp_client: SERPClient,
) -> Job | None:
    job = get_job(db_path, job_id)
    if job is None:
        return None
    results = serp_client.get_serp(job.topic)
    analysis = _analyze_serp(results, job.topic)
    updated = update_job(
        db_path,
        job_id,
        {
            "serp_raw": [r.model_dump() for r in results],
            "serp_analysis": analysis.model_dump(),
        },
    )
    return updated


def _build_outline_messages(job: Job) -> list[dict[str, str]]:
    system = (
        "You are an SEO content outline writer. Output only valid JSON with no markdown or explanation. "
        'Schema: {"sections": [{"heading_level": 1|2|3, "title": "...", "bullet_points": ["...", ...]}]}. '
        "Use exactly one H1 (heading_level 1). Use H2/H3 in order. bullet_points is optional per section."
    )
    parts = [f"Topic: {job.topic}. Target word count: {job.word_count}. Language: {job.language}."]
    if job.serp_analysis:
        if job.serp_analysis.themes:
            parts.append(f"Themes: {', '.join(job.serp_analysis.themes[:8])}.")
        if job.serp_analysis.subtopics:
            parts.append(f"Subtopics to consider: {', '.join(job.serp_analysis.subtopics[:5])}.")
        if job.serp_analysis.keyword_candidates:
            parts.append(f"Keyword candidates: {', '.join(job.serp_analysis.keyword_candidates[:10])}.")
    parts.append("Produce a content outline in the JSON schema above.")
    user = " ".join(parts)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def run_outline_step(
    job_id: uuid.UUID,
    db_path: str,
    llm_client: LLMClient,
) -> Job | None:
    job = get_job(db_path, job_id)
    if job is None:
        return None
    messages = _build_outline_messages(job)
    try:
        response = llm_client.generate(messages, options=GenerateOptions(json_mode=True))
        data = json.loads(response)
        outline = Outline.model_validate(data)
    except json.JSONDecodeError as e:
        update_job(db_path, job_id, {"error": f"Outline generation failed: invalid JSON ({e!s})"})
        return get_job(db_path, job_id)
    except ValidationError as e:
        update_job(db_path, job_id, {"error": f"Outline generation failed: validation error ({e!s})"})
        return get_job(db_path, job_id)
    update_job(db_path, job_id, {"outline": outline.model_dump(), "error": None})
    return get_job(db_path, job_id)


def _build_article_messages(job: Job) -> list[dict[str, str]]:
    primary = job.topic
    if job.serp_analysis and job.serp_analysis.keyword_candidates:
        primary = job.serp_analysis.keyword_candidates[0]
    system = (
        "You are an SEO content writer. Output only valid JSON with no markdown. "
        'Schema: {"sections": [{"level": 1|2|3, "heading": "...", "content": "..."}]}. '
        "Use exactly one section with level 1 (H1). Follow the outline. "
        f"Include the primary keyword \"{primary}\" in the H1 heading and in the first section content. "
        "Match target word count roughly. Write in the given language."
    )
    outline_desc = []
    for s in job.outline.sections:
        outline_desc.append(f"[H{s.heading_level}] {s.title}")
        for bp in (s.bullet_points or [])[:3]:
            outline_desc.append(f"  - {bp}")
    parts = [
        f"Topic: {job.topic}. Target word count: {job.word_count}. Language: {job.language}. Primary keyword: {primary}.",
        "Outline: " + " | ".join(outline_desc),
        "Produce a full article in the JSON schema above.",
    ]
    user = " ".join(parts)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def run_article_step(
    job_id: uuid.UUID,
    db_path: str,
    llm_client: LLMClient,
) -> Job | None:
    job = get_job(db_path, job_id)
    if job is None:
        return None
    if job.outline is None or not job.outline.sections:
        update_job(db_path, job_id, {"error": "Article generation failed: no outline"})
        return get_job(db_path, job_id)
    messages = _build_article_messages(job)
    try:
        response = llm_client.generate(messages, options=GenerateOptions(json_mode=True))
        data = json.loads(response)
        article = Article.model_validate(data)
    except json.JSONDecodeError as e:
        update_job(db_path, job_id, {"error": f"Article generation failed: invalid JSON ({e!s})"})
        return get_job(db_path, job_id)
    except ValidationError as e:
        update_job(db_path, job_id, {"error": f"Article generation failed: validation error ({e!s})"})
        return get_job(db_path, job_id)
    update_job(db_path, job_id, {"article": article.model_dump(), "error": None})
    return get_job(db_path, job_id)
