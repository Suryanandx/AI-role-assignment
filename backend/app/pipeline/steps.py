import uuid

from app.db import create_job
from app.models import CreateJobInput


def create_job_step(input: CreateJobInput, db_path: str) -> uuid.UUID:
    job = create_job(db_path, input)
    return job.id
