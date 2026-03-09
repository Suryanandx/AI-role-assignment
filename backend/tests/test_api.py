"""Tests for GraphQL API: createJob, job(id), runPipeline."""

import os
import tempfile
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app
from app.services import MockLLMClient, MockSERPClient


class _MultiResponseLLM:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    def generate(self, messages, *, options=None):
        if not self._responses:
            return "{}"
        return self._responses.pop(0)


def test_graphql_create_job_returns_id():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    os.environ["DB_PATH"] = path
    try:
        init_db(path)
        with (
            patch("app.api.context.get_serp_client", return_value=MockSERPClient()),
            patch("app.api.context.get_llm_client", return_value=MockLLMClient()),
        ):
            client = TestClient(app)
            response = client.post(
                "/graphql",
                json={
                    "query": "mutation($input: CreateJobInput!) { createJob(input: $input) }",
                    "variables": {"input": {"topic": "Test topic", "wordCount": 1000, "language": "en"}},
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data and "createJob" in data["data"]
        job_id = data["data"]["createJob"]
        assert isinstance(job_id, str)
        uuid.UUID(job_id)
    finally:
        os.environ.pop("DB_PATH", None)


def test_graphql_job_returns_job_by_id():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    os.environ["DB_PATH"] = path
    try:
        init_db(path)
        with (
            patch("app.api.context.get_serp_client", return_value=MockSERPClient()),
            patch("app.api.context.get_llm_client", return_value=MockLLMClient()),
        ):
            client = TestClient(app)
            create_resp = client.post(
                "/graphql",
                json={
                    "query": "mutation($input: CreateJobInput!) { createJob(input: $input) }",
                    "variables": {"input": {"topic": "Query test"}},
                },
            )
            assert create_resp.status_code == 200
            job_id = create_resp.json()["data"]["createJob"]
            query_resp = client.post(
                "/graphql",
                json={
                    "query": "query($id: ID!) { job(id: $id) { id status topic } }",
                    "variables": {"id": job_id},
                },
            )
        assert query_resp.status_code == 200
        job_data = query_resp.json()["data"]["job"]
        assert job_data is not None
        assert job_data["id"] == job_id
        assert job_data["status"] == "pending"
        assert job_data["topic"] == "Query test"
    finally:
        os.environ.pop("DB_PATH", None)


def test_graphql_job_nonexistent_returns_null():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    os.environ["DB_PATH"] = path
    try:
        init_db(path)
        with (
            patch("app.api.context.get_serp_client", return_value=MockSERPClient()),
            patch("app.api.context.get_llm_client", return_value=MockLLMClient()),
        ):
            client = TestClient(app)
            response = client.post(
                "/graphql",
                json={
                    "query": "query($id: ID!) { job(id: $id) { id } }",
                    "variables": {"id": str(uuid.uuid4())},
                },
            )
        assert response.status_code == 200
        assert response.json()["data"]["job"] is None
    finally:
        os.environ.pop("DB_PATH", None)


def test_graphql_run_pipeline_returns_job():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    os.environ["DB_PATH"] = path
    try:
        init_db(path)
        outline = '{"sections":[{"heading_level":1,"title":"Intro","bullet_points":[]}]}'
        article = '{"sections":[{"level":1,"heading":"Run test","content":"Content."}]}'
        metadata = (
            '{"title_tag":"T","meta_description":"D.",'
            '"primary_keyword":"Run test","secondary_keywords":[],'
            '"internal_links":[{"anchor_text":"a","target_topic":"b"}],'
            '"external_refs":[{"url":"https://x.com","title":"X","placement_context":"c"}]}'
        )
        faq = '[{"question":"Q?","answer":"A."}]'
        llm = _MultiResponseLLM([outline, article, metadata, faq])
        with (
            patch("app.api.context.get_serp_client", return_value=MockSERPClient()),
            patch("app.api.context.get_llm_client", return_value=llm),
        ):
            client = TestClient(app)
            create_resp = client.post(
                "/graphql",
                json={
                    "query": "mutation($input: CreateJobInput!) { createJob(input: $input) }",
                    "variables": {"input": {"topic": "Run test"}},
                },
            )
            assert create_resp.status_code == 200
            job_id = create_resp.json()["data"]["createJob"]
            run_resp = client.post(
                "/graphql",
                json={
                    "query": "mutation($jobId: ID!) { runPipeline(jobId: $jobId) { id status topic article { sections { heading } } } }",
                    "variables": {"jobId": job_id},
                },
            )
        assert run_resp.status_code == 200
        run_data = run_resp.json()["data"]["runPipeline"]
        assert run_data is not None
        assert run_data["id"] == job_id
        assert run_data["status"] in ("completed", "failed")
        assert run_data["topic"] == "Run test"
        if run_data["article"]:
            assert len(run_data["article"]["sections"]) >= 1
    finally:
        os.environ.pop("DB_PATH", None)
