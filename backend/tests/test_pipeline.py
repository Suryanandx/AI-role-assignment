import tempfile
import uuid

from app.db import get_job, init_db
from app.models import CreateJobInput, JobStatus
from app.pipeline import create_job_step, run_serp_step
from app.services import MockSERPClient


def test_create_job_step_returns_uuid_and_persists():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    inp = CreateJobInput(topic="Test", word_count=1000, language="en")
    job_id = create_job_step(inp, path)
    assert isinstance(job_id, uuid.UUID)
    job = get_job(path, job_id)
    assert job is not None
    assert job.status == JobStatus.pending
    assert job.topic == "Test"
    assert job.word_count == 1000
    assert job.language == "en"


def test_create_job_step_two_calls_yield_different_ids():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    id1 = create_job_step(CreateJobInput(topic="A", word_count=500, language="en"), path)
    id2 = create_job_step(CreateJobInput(topic="B", word_count=2000, language="de"), path)
    assert id1 != id2
    assert get_job(path, id1).topic == "A"
    assert get_job(path, id2).topic == "B"


def test_run_serp_step_persists_serp_raw_and_analysis():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(
        CreateJobInput(topic="best productivity tools", word_count=1500, language="en"),
        path,
    )
    job = run_serp_step(job_id, path, MockSERPClient())
    assert job is not None
    assert job.serp_raw is not None
    assert len(job.serp_raw) == 10
    assert job.serp_analysis is not None
    assert len(job.serp_analysis.themes) > 0
    assert len(job.serp_analysis.keyword_candidates) > 0
    assert len(job.serp_analysis.subtopics) > 0
    combined = " ".join(job.serp_analysis.themes + job.serp_analysis.keyword_candidates).lower()
    assert "productivity" in combined or "tools" in combined


def test_run_serp_step_unknown_job_returns_none():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    result = run_serp_step(uuid.uuid4(), path, MockSERPClient())
    assert result is None


def test_run_serp_step_deterministic_overwrites():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="test topic", word_count=1000, language="en"), path)
    job1 = run_serp_step(job_id, path, MockSERPClient())
    assert job1 is not None
    themes1 = job1.serp_analysis.themes if job1.serp_analysis else []
    job2 = run_serp_step(job_id, path, MockSERPClient())
    assert job2 is not None
    themes2 = job2.serp_analysis.themes if job2.serp_analysis else []
    assert themes1 == themes2
