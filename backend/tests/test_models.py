import uuid

import pytest

from app.models import (
    Article,
    ArticleSection,
    CreateJobInput,
    ExternalRef,
    FAQItem,
    InternalLink,
    Job,
    JobStatus,
    Outline,
    OutlineSection,
    SEOMetadata,
    SERPAnalysis,
    SERPResult,
)


def test_serp_result_serialization():
    r = SERPResult(rank=1, url="https://example.com", title="Test", snippet="Snippet.")
    assert r.model_dump()["rank"] == 1
    assert "Test" in r.model_dump_json()


def test_serp_analysis_defaults():
    a = SERPAnalysis()
    assert a.themes == []
    a = SERPAnalysis(themes=["a"], keyword_candidates=["k"])
    assert a.themes == ["a"] and a.keyword_candidates == ["k"]


def test_outline_section():
    s = OutlineSection(heading_level=1, title="Intro", bullet_points=["Point 1"])
    assert s.heading_level == 1
    with pytest.raises(ValueError):
        OutlineSection(heading_level=4, title="Bad", bullet_points=[])


def test_outline():
    o = Outline(sections=[OutlineSection(heading_level=1, title="H1", bullet_points=[])])
    assert len(o.sections) == 1


def test_article_section():
    s = ArticleSection(level=2, heading="Section", content="Body.")
    assert s.level == 2


def test_article():
    a = Article(sections=[ArticleSection(level=1, heading="Title", content="Intro.")])
    assert len(a.sections) == 1


def test_seo_metadata():
    m = SEOMetadata(
        title_tag="Title",
        meta_description="Desc",
        primary_keyword="kw",
        secondary_keywords=["a", "b"],
    )
    assert m.primary_keyword == "kw"


def test_internal_link():
    l = InternalLink(anchor_text="click", target_topic="/page")
    assert l.anchor_text == "click"


def test_external_ref():
    e = ExternalRef(url="https://x.com", title="Ref", placement_context="After intro")
    assert e.url == "https://x.com"


def test_faq_item():
    f = FAQItem(question="Q?", answer="A.")
    assert f.question == "Q?"


def test_create_job_input():
    i = CreateJobInput(topic="tools")
    assert i.word_count == 1500 and i.language == "en"


def test_job_minimal():
    j = Job(status=JobStatus.pending, topic="test", word_count=1000, language="en")
    assert j.status == JobStatus.pending
    assert j.serp_raw is None
    assert j.internal_links == []
    assert isinstance(j.id, uuid.UUID)
    assert j.created_at is not None


def test_job_serialization_roundtrip():
    j = Job(status=JobStatus.completed, topic="t", word_count=500, language="en")
    d = j.model_dump()
    j2 = Job.model_validate(d)
    assert j2.topic == j.topic and j2.status == j.status
