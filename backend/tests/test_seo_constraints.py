"""SEO constraint tests: validate rules against deterministic Job fixtures. No DB/LLM/SERP."""

from app.models import (
    Article,
    ArticleSection,
    ExternalRef,
    InternalLink,
    Job,
    JobStatus,
    SEOMetadata,
)

FIRST_N_WORDS = 100


def _primary_keyword(job: Job) -> str:
    if job.metadata:
        return job.metadata.primary_keyword
    return job.topic


def _has_exactly_one_h1(job: Job) -> bool:
    if not job.article or not job.article.sections:
        return False
    return sum(1 for s in job.article.sections if s.level == 1) == 1


def _primary_keyword_in_title(job: Job) -> bool:
    if not job.metadata or not job.metadata.title_tag:
        return False
    kw = _primary_keyword(job).lower()
    return kw in (job.metadata.title_tag or "").lower()


def _primary_keyword_in_first_n_words(job: Job, n: int = FIRST_N_WORDS) -> bool:
    if not job.article or not job.article.sections:
        return False
    first_content = (job.article.sections[0].content or "").strip()
    words = first_content.split()[:n]
    text = " ".join(words).lower()
    return _primary_keyword(job).lower() in text


def _meta_description_length_ok(job: Job) -> bool:
    if not job.metadata or not job.metadata.meta_description:
        return False
    length = len((job.metadata.meta_description or "").strip())
    return 150 <= length <= 160


def _internal_links_count_ok(job: Job) -> bool:
    count = len(job.internal_links or [])
    return 3 <= count <= 5


def _external_refs_count_ok(job: Job) -> bool:
    count = len(job.external_refs or [])
    return 2 <= count <= 4


def _heading_hierarchy_valid(job: Job) -> bool:
    if not job.article or not job.article.sections:
        return False
    levels = [s.level for s in job.article.sections]
    if levels[0] != 1:
        return False
    return all(levels[i] <= levels[i + 1] for i in range(len(levels) - 1))


def _compliant_job() -> Job:
    primary = "Best Productivity Tools"
    meta_desc = "Discover the best productivity tools for remote teams. Compare features, pricing, and workflows. " * 2
    meta_desc = meta_desc[:158]
    return Job(
        status=JobStatus.completed,
        topic=primary,
        word_count=1500,
        language="en",
        article=Article(
            sections=[
                ArticleSection(
                    level=1,
                    heading=f"{primary} in 2025",
                    content=f"{primary} help you get more done. Here is a short intro that includes the keyword early.",
                ),
                ArticleSection(level=2, heading="Top picks", content="Section two."),
                ArticleSection(level=2, heading="Comparison", content="Section three."),
            ]
        ),
        metadata=SEOMetadata(
            title_tag=f"{primary} | Guide 2025",
            meta_description=meta_desc,
            primary_keyword=primary,
            secondary_keywords=[],
        ),
        internal_links=[
            InternalLink(anchor_text="link one", target_topic="topic1"),
            InternalLink(anchor_text="link two", target_topic="topic2"),
            InternalLink(anchor_text="link three", target_topic="topic3"),
        ],
        external_refs=[
            ExternalRef(url="https://a.com", title="Source A", placement_context="intro"),
            ExternalRef(url="https://b.com", title="Source B", placement_context="body"),
        ],
    )


def test_seo_compliant_job_passes_all_rules():
    job = _compliant_job()
    assert _has_exactly_one_h1(job)
    assert _primary_keyword_in_title(job)
    assert _primary_keyword_in_first_n_words(job)
    assert _meta_description_length_ok(job)
    assert _internal_links_count_ok(job)
    assert _external_refs_count_ok(job)
    assert _heading_hierarchy_valid(job)


def test_seo_exactly_one_h1():
    compliant = _compliant_job()
    assert _has_exactly_one_h1(compliant) is True
    two_h1 = Job(
        status=JobStatus.completed,
        topic="X",
        word_count=1500,
        language="en",
        article=Article(
            sections=[
                ArticleSection(level=1, heading="First H1", content="A."),
                ArticleSection(level=1, heading="Second H1", content="B."),
            ]
        ),
    )
    assert _has_exactly_one_h1(two_h1) is False


def test_seo_primary_keyword_in_title():
    compliant = _compliant_job()
    assert _primary_keyword_in_title(compliant) is True
    no_kw = _compliant_job()
    no_kw.metadata = SEOMetadata(
        title_tag="Random Title Without Keyword",
        meta_description=no_kw.metadata.meta_description,
        primary_keyword="Best Productivity Tools",
        secondary_keywords=[],
    )
    assert _primary_keyword_in_title(no_kw) is False


def test_seo_primary_keyword_in_first_n_words():
    compliant = _compliant_job()
    assert _primary_keyword_in_first_n_words(compliant) is True
    late_kw = _compliant_job()
    late_kw.article.sections[0].content = "This intro has no keyword. " * 30 + "Best Productivity Tools at the end."
    assert _primary_keyword_in_first_n_words(late_kw, n=50) is False


def test_seo_meta_description_length():
    compliant = _compliant_job()
    assert _meta_description_length_ok(compliant) is True
    short_meta = _compliant_job()
    short_meta.metadata.meta_description = "Short."
    assert _meta_description_length_ok(short_meta) is False
    long_meta = _compliant_job()
    long_meta.metadata.meta_description = "X" * 200
    assert _meta_description_length_ok(long_meta) is False


def test_seo_internal_links_count():
    compliant = _compliant_job()
    assert _internal_links_count_ok(compliant) is True
    one_link = _compliant_job()
    one_link.internal_links = [InternalLink(anchor_text="a", target_topic="b")]
    assert _internal_links_count_ok(one_link) is False
    six_links = _compliant_job()
    six_links.internal_links = [
        InternalLink(anchor_text=f"l{i}", target_topic=f"t{i}") for i in range(6)
    ]
    assert _internal_links_count_ok(six_links) is False


def test_seo_external_refs_count():
    compliant = _compliant_job()
    assert _external_refs_count_ok(compliant) is True
    one_ref = _compliant_job()
    one_ref.external_refs = [
        ExternalRef(url="https://x.com", title="X", placement_context="c")
    ]
    assert _external_refs_count_ok(one_ref) is False
    five_refs = _compliant_job()
    five_refs.external_refs = [
        ExternalRef(url=f"https://x{i}.com", title=f"X{i}", placement_context="c")
        for i in range(5)
    ]
    assert _external_refs_count_ok(five_refs) is False


def test_seo_heading_hierarchy():
    compliant = _compliant_job()
    assert _heading_hierarchy_valid(compliant) is True
    h2_first = Job(
        status=JobStatus.completed,
        topic="X",
        word_count=1500,
        language="en",
        article=Article(
            sections=[
                ArticleSection(level=2, heading="H2 first", content="A."),
                ArticleSection(level=1, heading="H1 second", content="B."),
            ]
        ),
    )
    assert _heading_hierarchy_valid(h2_first) is False
    h3_before_h2 = Job(
        status=JobStatus.completed,
        topic="X",
        word_count=1500,
        language="en",
        article=Article(
            sections=[
                ArticleSection(level=1, heading="H1", content="A."),
                ArticleSection(level=3, heading="H3 before H2", content="B."),
                ArticleSection(level=2, heading="H2", content="C."),
            ]
        ),
    )
    assert _heading_hierarchy_valid(h3_before_h2) is False
