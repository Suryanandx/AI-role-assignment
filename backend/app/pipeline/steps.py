import re
import uuid

from app.db import create_job, get_job, update_job
from app.models import CreateJobInput, Job, SERPAnalysis, SERPResult
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
