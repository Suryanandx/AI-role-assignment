import tempfile
import uuid

from app.db import get_job, init_db
from app.models import CreateJobInput, JobStatus
from app.pipeline import create_job_step


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
