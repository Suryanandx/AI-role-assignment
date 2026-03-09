import tempfile
import uuid

import pytest

from app.db import create_job, get_job, init_db, update_job
from app.models import CreateJobInput, JobStatus


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path


def test_init_and_create_job(db_path):
    init_db(db_path)
    inp = CreateJobInput(topic="test topic", word_count=1000, language="en")
    job = create_job(db_path, inp)
    assert job.id is not None
    assert job.status == JobStatus.pending
    assert job.topic == "test topic"
    assert job.word_count == 1000
    assert job.language == "en"
    assert job.serp_raw is None
    assert job.created_at is not None
    assert job.updated_at is not None


def test_get_job_returns_same_job(db_path):
    init_db(db_path)
    inp = CreateJobInput(topic="get me", word_count=500, language="en")
    created = create_job(db_path, inp)
    fetched = get_job(db_path, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.topic == created.topic
    assert fetched.status == created.status


def test_get_job_unknown_id_returns_none(db_path):
    init_db(db_path)
    assert get_job(db_path, uuid.uuid4()) is None
    assert get_job(db_path, str(uuid.uuid4())) is None


def test_update_job_status(db_path):
    init_db(db_path)
    job = create_job(db_path, CreateJobInput(topic="update", word_count=1500, language="en"))
    updated = update_job(db_path, job.id, {"status": "running"})
    assert updated is not None
    assert updated.status == JobStatus.running
    assert updated.updated_at >= job.updated_at
    fetched = get_job(db_path, job.id)
    assert fetched.status == JobStatus.running


def test_update_job_serp_raw_roundtrip(db_path):
    init_db(db_path)
    job = create_job(db_path, CreateJobInput(topic="serp", word_count=1000, language="en"))
    serp_raw = [
        {"rank": 1, "url": "https://a.com", "title": "A", "snippet": "S1"},
        {"rank": 2, "url": "https://b.com", "title": "B", "snippet": "S2"},
    ]
    updated = update_job(db_path, job.id, {"serp_raw": serp_raw})
    assert updated is not None
    assert updated.serp_raw is not None
    assert len(updated.serp_raw) == 2
    assert updated.serp_raw[0].title == "A"
    fetched = get_job(db_path, job.id)
    assert len(fetched.serp_raw) == 2
    assert fetched.serp_raw[1].url == "https://b.com"


def test_update_job_full_roundtrip(db_path):
    init_db(db_path)
    job = create_job(db_path, CreateJobInput(topic="full", word_count=1200, language="en"))
    update_job(db_path, job.id, {
        "status": "completed",
        "serp_analysis": {"themes": ["t1"], "subtopics": ["s1"], "paa_questions": [], "keyword_candidates": ["k1"]},
        "outline": {"sections": [{"heading_level": 1, "title": "Intro", "bullet_points": ["p1"]}]},
        "article": {"sections": [{"level": 1, "heading": "H1", "content": "Body."}]},
        "metadata": {"title_tag": "Title", "meta_description": "Desc", "primary_keyword": "kw", "secondary_keywords": []},
        "internal_links": [{"anchor_text": "link", "target_topic": "/page"}],
        "external_refs": [{"url": "https://x.com", "title": "Ref", "placement_context": "After intro"}],
        "quality_score": 0.85,
        "faq": [{"question": "Q?", "answer": "A."}],
        "error": None,
    })
    fetched = get_job(db_path, job.id)
    assert fetched.status == JobStatus.completed
    assert fetched.serp_analysis is not None and fetched.serp_analysis.themes == ["t1"]
    assert fetched.outline is not None and len(fetched.outline.sections) == 1
    assert fetched.article is not None and len(fetched.article.sections) == 1
    assert fetched.metadata is not None and fetched.metadata.title_tag == "Title"
    assert len(fetched.internal_links) == 1 and fetched.internal_links[0].anchor_text == "link"
    assert len(fetched.external_refs) == 1 and fetched.external_refs[0].url == "https://x.com"
    assert fetched.quality_score == 0.85
    assert fetched.faq is not None and len(fetched.faq) == 1 and fetched.faq[0].question == "Q?"


def test_update_job_unknown_id_returns_none(db_path):
    init_db(db_path)
    assert update_job(db_path, uuid.uuid4(), {"status": "running"}) is None
