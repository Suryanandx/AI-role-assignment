import json
import re
import statistics
import uuid

from pydantic import ValidationError

from app.config import Settings
from app.db import create_job, get_job, update_job
from app.models import (
    Article,
    CreateJobInput,
    ExternalRef,
    FAQItem,
    InternalLink,
    Job,
    JobStatus,
    Outline,
    SEOMetadata,
    SERPAnalysis,
    SERPResult,
)
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


def _build_metadata_messages(job: Job) -> list[dict[str, str]]:
    primary = job.topic
    if job.serp_analysis and job.serp_analysis.keyword_candidates:
        primary = job.serp_analysis.keyword_candidates[0]
    first_heading = job.article.sections[0].heading if job.article.sections else ""
    first_content = (job.article.sections[0].content[:300] + "...") if job.article.sections and job.article.sections[0].content else ""
    system = (
        "You are an SEO specialist. Output only valid JSON with no markdown. "
        "Single object with keys: title_tag (string, max 60 chars, primary keyword near front), "
        "meta_description (string, 150-160 chars, include primary keyword and brief CTA), "
        "primary_keyword (string), secondary_keywords (array of strings), "
        "internal_links (array of {anchor_text, target_topic}, 3-5 items), "
        "external_refs (array of {url, title, placement_context}, 2-4 items)."
    )
    user = (
        f"Topic: {job.topic}. Primary keyword: {primary}. "
        f"Article H1: {first_heading}. First paragraph summary: {first_content} "
        "Produce the JSON object above."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def run_metadata_step(
    job_id: uuid.UUID,
    db_path: str,
    llm_client: LLMClient,
) -> Job | None:
    job = get_job(db_path, job_id)
    if job is None:
        return None
    if job.article is None or not job.article.sections:
        update_job(db_path, job_id, {"error": "Metadata step failed: no article"})
        return get_job(db_path, job_id)
    messages = _build_metadata_messages(job)
    try:
        response = llm_client.generate(messages, options=GenerateOptions(json_mode=True))
        data = json.loads(response)
        title_tag = (data.get("title_tag") or "")[:60].strip()
        meta_desc = (data.get("meta_description") or "")[:160].strip()
        primary_kw = data.get("primary_keyword") or job.topic
        secondary_kw = data.get("secondary_keywords") or []
        if not title_tag:
            title_tag = primary_kw[:60]
        if not meta_desc:
            meta_desc = f"Learn about {primary_kw}. Read more."
        metadata = SEOMetadata(
            title_tag=title_tag,
            meta_description=meta_desc,
            primary_keyword=primary_kw,
            secondary_keywords=secondary_kw[:15],
        )
        internal_links = [InternalLink.model_validate(x) for x in data.get("internal_links", [])][:5]
        external_refs = [ExternalRef.model_validate(x) for x in data.get("external_refs", [])][:4]
    except json.JSONDecodeError as e:
        update_job(db_path, job_id, {"error": f"Metadata step failed: invalid JSON ({e!s})"})
        return get_job(db_path, job_id)
    except (ValidationError, KeyError) as e:
        update_job(db_path, job_id, {"error": f"Metadata step failed: validation error ({e!s})"})
        return get_job(db_path, job_id)
    update_job(
        db_path,
        job_id,
        {
            "metadata": metadata.model_dump(),
            "internal_links": [l.model_dump() for l in internal_links],
            "external_refs": [r.model_dump() for r in external_refs],
            "error": None,
        },
    )
    return get_job(db_path, job_id)


def _sentences_and_word_counts(text: str) -> list[int]:
    """Split text into sentences and return word count per sentence."""
    if not (text or text.strip()):
        return []
    parts = re.split(r"[.!?]+\s*", text)
    return [len(s.split()) for s in parts if s.strip()]


def _compute_quality_score(job: Job) -> float:
    """Rule-based SEO checks; returns a score in [0.0, 1.0]."""
    scores: list[float] = []
    article = job.article
    if not article or not article.sections:
        return 0.0

    primary = job.topic
    if job.metadata:
        primary = job.metadata.primary_keyword
    elif job.serp_analysis and job.serp_analysis.keyword_candidates:
        primary = job.serp_analysis.keyword_candidates[0]
    primary_lower = primary.lower()

    first = article.sections[0]
    h1_count = sum(1 for s in article.sections if s.level == 1)

    if primary_lower in (first.heading or "").lower():
        scores.append(1.0)
    else:
        scores.append(0.0)

    intro = (first.content or "")[:500]
    if primary_lower in intro.lower():
        scores.append(1.0)
    else:
        scores.append(0.0)

    if h1_count == 1:
        scores.append(1.0)
    else:
        scores.append(0.0)

    first_is_h1 = first.level == 1
    no_other_h1 = h1_count <= 1
    if first_is_h1 and no_other_h1:
        scores.append(1.0)
    else:
        scores.append(0.0)

    if job.metadata:
        tt_len = len((job.metadata.title_tag or "").strip())
        if 1 <= tt_len <= 60:
            scores.append(1.0)
        elif tt_len <= 70:
            scores.append(0.5)
        else:
            scores.append(0.0)
        md_len = len((job.metadata.meta_description or "").strip())
        if 150 <= md_len <= 160:
            scores.append(1.0)
        elif 140 <= md_len <= 165:
            scores.append(0.5)
        else:
            scores.append(0.0)
    else:
        scores.extend([0.0, 0.0])

    n_internal = len(job.internal_links or [])
    if 3 <= n_internal <= 5:
        scores.append(1.0)
    elif 1 <= n_internal <= 5:
        scores.append(0.5)
    else:
        scores.append(0.0)

    n_external = len(job.external_refs or [])
    if 2 <= n_external <= 4:
        scores.append(1.0)
    elif n_external == 1:
        scores.append(0.5)
    else:
        scores.append(0.0)

    all_content = " ".join(s.content or "" for s in article.sections)
    word_counts = _sentences_and_word_counts(all_content)
    if len(word_counts) >= 2:
        try:
            stdev = statistics.stdev(word_counts)
            if stdev >= 2.0:
                scores.append(1.0)
            elif stdev >= 0.5:
                scores.append(0.5)
            else:
                scores.append(0.0)
        except statistics.StatisticsError:
            scores.append(0.5)
    else:
        scores.append(0.5)

    max_sentences_per_section = 10
    any_too_dense = False
    for s in article.sections:
        n = len(_sentences_and_word_counts(s.content or ""))
        if n > max_sentences_per_section:
            any_too_dense = True
            break
    scores.append(0.0 if any_too_dense else 1.0)

    has_two_sections = len(article.sections) >= 2
    first_has_content = bool((first.content or "").strip())
    has_h2 = any(s.level == 2 for s in article.sections)
    if has_two_sections and first_has_content and has_h2:
        scores.append(1.0)
    elif has_two_sections and first_has_content:
        scores.append(0.5)
    else:
        scores.append(0.0)

    levels = [s.level for s in article.sections]
    non_decreasing = all(levels[i] <= levels[i + 1] for i in range(len(levels) - 1))
    first_is_one = levels[0] == 1 if levels else False
    scores.append(1.0 if (non_decreasing and first_is_one) else 0.0)

    return sum(scores) / len(scores) if scores else 0.0


def run_validation_step(job_id: uuid.UUID, db_path: str) -> Job | None:
    job = get_job(db_path, job_id)
    if job is None:
        return None
    if job.article is None or not job.article.sections:
        update_job(db_path, job_id, {"error": "Validation step failed: no article"})
        return get_job(db_path, job_id)
    score = _compute_quality_score(job)
    update_job(db_path, job_id, {"quality_score": score, "error": None})
    return get_job(db_path, job_id)


def _revision_reason(job: Job, score: float) -> str:
    """Return a short targeted reason for revision when score is below threshold."""
    if not job.article or not job.article.sections:
        return "improve SEO and clarity of the intro"
    primary = job.topic
    if job.metadata:
        primary = job.metadata.primary_keyword
    elif job.serp_analysis and job.serp_analysis.keyword_candidates:
        primary = job.serp_analysis.keyword_candidates[0]
    primary_lower = primary.lower()
    first = job.article.sections[0]
    intro = (first.content or "")[:500]
    if primary_lower not in intro.lower():
        return "improve intro for keyword density"
    if primary_lower not in (first.heading or "").lower():
        return "include primary keyword in the main heading"
    levels = [s.level for s in job.article.sections]
    if levels and levels[0] != 1:
        return "ensure the first heading is H1"
    non_decreasing = all(levels[i] <= levels[i + 1] for i in range(len(levels) - 1))
    if not non_decreasing:
        return "fix heading order so levels do not skip"
    return "improve SEO and clarity of the intro"


def _build_revision_messages(job: Job, reason: str) -> list[dict[str, str]]:
    primary = job.topic
    if job.metadata:
        primary = job.metadata.primary_keyword
    elif job.serp_analysis and job.serp_analysis.keyword_candidates:
        primary = job.serp_analysis.keyword_candidates[0]
    first_content = ""
    if job.article and job.article.sections:
        first_content = (job.article.sections[0].content or "")[:800]
    system = (
        "You are an SEO content specialist. Output only valid JSON with no markdown. "
        "Single object with one key: sections (array of objects with level, heading, content). "
        "Revise the article to address the instruction; keep the same number of sections and structure."
    )
    user = (
        f"Primary keyword: {primary}. Instruction: {reason}. "
        f"Current first section content: {first_content} "
        "Output the full revised article as JSON: {\"sections\": [{\"level\": 1, \"heading\": \"...\", \"content\": \"...\"}, ...]}."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def run_revision_step(
    job_id: uuid.UUID,
    db_path: str,
    llm_client: LLMClient,
    reason: str,
) -> Job | None:
    job = get_job(db_path, job_id)
    if job is None:
        return None
    if job.article is None or not job.article.sections:
        update_job(db_path, job_id, {"error": "Revision step failed: no article"})
        return get_job(db_path, job_id)
    messages = _build_revision_messages(job, reason)
    try:
        response = llm_client.generate(messages, options=GenerateOptions(json_mode=True))
        data = json.loads(response)
        article = Article.model_validate(data)
    except json.JSONDecodeError as e:
        update_job(db_path, job_id, {"error": f"Revision step failed: invalid JSON ({e!s})"})
        return get_job(db_path, job_id)
    except ValidationError as e:
        update_job(db_path, job_id, {"error": f"Revision step failed: validation error ({e!s})"})
        return get_job(db_path, job_id)
    if not article.sections:
        update_job(db_path, job_id, {"error": "Revision step failed: no sections in response"})
        return get_job(db_path, job_id)
    update_job(db_path, job_id, {"article": article.model_dump(), "error": None})
    return get_job(db_path, job_id)


def _build_faq_messages(job: Job) -> list[dict[str, str]]:
    system = (
        "You are an SEO content assistant. Output only valid JSON: an array of FAQ objects, "
        'each with "question" and "answer" (strings). Produce 3 to 5 FAQs relevant to the topic. '
        "Use the given PAA-style questions when provided; write concise answers (1 to 3 sentences)."
    )
    parts = [f"Topic: {job.topic}."]
    if job.serp_analysis and job.serp_analysis.paa_questions:
        parts.append(f"PAA questions to use or adapt: {', '.join(job.serp_analysis.paa_questions[:5])}.")
    else:
        parts.append("Suggest 3 to 5 common questions for this topic and answer them.")
    if job.article and job.article.sections:
        excerpt = job.article.sections[0].content[:400].strip() if job.article.sections[0].content else ""
        if excerpt:
            parts.append(f"Article excerpt for context: {excerpt}")
    parts.append("Output a JSON array of objects with question and answer keys only.")
    user = " ".join(parts)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def run_faq_step(
    job_id: uuid.UUID,
    db_path: str,
    llm_client: LLMClient,
) -> Job | None:
    job = get_job(db_path, job_id)
    if job is None:
        return None
    has_serp = job.serp_analysis is not None
    has_article = job.article is not None and job.article.sections
    if not has_serp and not has_article:
        update_job(db_path, job_id, {"error": "FAQ step failed: no SERP analysis or article"})
        return get_job(db_path, job_id)
    messages = _build_faq_messages(job)
    try:
        response = llm_client.generate(messages, options=GenerateOptions(json_mode=True))
        data = json.loads(response)
        if isinstance(data, dict) and "items" in data:
            raw_list = data["items"]
        elif isinstance(data, list):
            raw_list = data
        else:
            raw_list = []
        faq_list = [FAQItem.model_validate(x) for x in raw_list][:5]
    except json.JSONDecodeError as e:
        update_job(db_path, job_id, {"error": f"FAQ step failed: invalid JSON ({e!s})"})
        return get_job(db_path, job_id)
    except (ValidationError, KeyError, TypeError) as e:
        update_job(db_path, job_id, {"error": f"FAQ step failed: validation error ({e!s})"})
        return get_job(db_path, job_id)
    update_job(db_path, job_id, {"faq": [f.model_dump() for f in faq_list], "error": None})
    return get_job(db_path, job_id)


def run_pipeline(
    job_id: uuid.UUID,
    db_path: str,
    serp_client: SERPClient,
    llm_client: LLMClient,
) -> Job | None:
    job = get_job(db_path, job_id)
    if job is None:
        return None
    update_job(db_path, job_id, {"status": JobStatus.running})

    if job.serp_analysis is None:
        result = run_serp_step(job_id, db_path, serp_client)
        if result is None:
            update_job(db_path, job_id, {"status": JobStatus.failed})
            return get_job(db_path, job_id)
        job = result
        if job.error is not None:
            update_job(db_path, job_id, {"status": JobStatus.failed})
            return get_job(db_path, job_id)

    if job.outline is None:
        result = run_outline_step(job_id, db_path, llm_client)
        if result is None:
            update_job(db_path, job_id, {"status": JobStatus.failed})
            return get_job(db_path, job_id)
        job = result
        if job.error is not None:
            update_job(db_path, job_id, {"status": JobStatus.failed})
            return get_job(db_path, job_id)

    if job.article is None:
        result = run_article_step(job_id, db_path, llm_client)
        if result is None:
            update_job(db_path, job_id, {"status": JobStatus.failed})
            return get_job(db_path, job_id)
        job = result
        if job.error is not None:
            update_job(db_path, job_id, {"status": JobStatus.failed})
            return get_job(db_path, job_id)

    if job.metadata is None:
        result = run_metadata_step(job_id, db_path, llm_client)
        if result is None:
            update_job(db_path, job_id, {"status": JobStatus.failed})
            return get_job(db_path, job_id)
        job = result
        if job.error is not None:
            update_job(db_path, job_id, {"status": JobStatus.failed})
            return get_job(db_path, job_id)

    if job.faq is None:
        result = run_faq_step(job_id, db_path, llm_client)
        if result is None:
            update_job(db_path, job_id, {"status": JobStatus.failed})
            return get_job(db_path, job_id)
        job = result
        if job.error is not None:
            update_job(db_path, job_id, {"status": JobStatus.failed})
            return get_job(db_path, job_id)

    result = run_validation_step(job_id, db_path)
    if result is None:
        update_job(db_path, job_id, {"status": JobStatus.failed})
        return get_job(db_path, job_id)
    job = result
    if job.error is not None:
        update_job(db_path, job_id, {"status": JobStatus.failed})
        return get_job(db_path, job_id)

    settings = Settings()
    if job.quality_score is not None and job.quality_score < settings.quality_score_threshold:
        reason = _revision_reason(job, job.quality_score)
        result = run_revision_step(job_id, db_path, llm_client, reason)
        if result is None:
            update_job(db_path, job_id, {"status": JobStatus.failed})
            return get_job(db_path, job_id)
        job = result
        if job.error is not None:
            update_job(db_path, job_id, {"status": JobStatus.failed})
            return get_job(db_path, job_id)
        result = run_validation_step(job_id, db_path)
        if result is None:
            update_job(db_path, job_id, {"status": JobStatus.failed})
            return get_job(db_path, job_id)
        job = result
        if job.error is not None:
            update_job(db_path, job_id, {"status": JobStatus.failed})
            return get_job(db_path, job_id)

    update_job(db_path, job_id, {"status": JobStatus.completed})
    return get_job(db_path, job_id)
