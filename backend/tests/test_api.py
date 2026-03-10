"""Tests for GraphQL API: createJob, job(id), jobs(limit, offset), runPipeline."""

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


def test_graphql_jobs_list_returns_recent_first():
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
            for topic in ["First job", "Second job", "Third job"]:
                client.post(
                    "/graphql",
                    json={
                        "query": "mutation($input: CreateJobInput!) { createJob(input: $input) }",
                        "variables": {"input": {"topic": topic, "wordCount": 500, "language": "en"}},
                    },
                )
            resp = client.post(
                "/graphql",
                json={
                    "query": "query { jobs(limit: 2) { id topic } }",
                },
            )
        assert resp.status_code == 200
        data = resp.json()["data"]["jobs"]
        assert len(data) == 2
        assert data[0]["topic"] == "Third job"
        assert data[1]["topic"] == "Second job"
    finally:
        os.environ.pop("DB_PATH", None)


def test_graphql_jobs_list_respects_limit_and_offset():
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
            for topic in ["A", "B", "C"]:
                client.post(
                    "/graphql",
                    json={
                        "query": "mutation($input: CreateJobInput!) { createJob(input: $input) }",
                        "variables": {"input": {"topic": topic}},
                    },
                )
            resp = client.post(
                "/graphql",
                json={
                    "query": "query { jobs(limit: 1, offset: 1) { id topic } }",
                },
            )
        assert resp.status_code == 200
        data = resp.json()["data"]["jobs"]
        assert len(data) == 1
        assert data[0]["topic"] == "B"
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


def test_graphql_job_article_with_faq_returns_sections_and_faq():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    os.environ["DB_PATH"] = path
    try:
        init_db(path)
        outline = '{"sections":[{"heading_level":1,"title":"Intro","bullet_points":[]}]}'
        article = '{"sections":[{"level":1,"heading":"FAQ output","content":"Content here."}]}'
        metadata = (
            '{"title_tag":"T","meta_description":"D.",'
            '"primary_keyword":"K","secondary_keywords":[],'
            '"internal_links":[{"anchor_text":"a","target_topic":"b"}],'
            '"external_refs":[{"url":"https://x.com","title":"X","placement_context":"c"}]}'
        )
        faq = '[{"question":"What is it?","answer":"An answer."}]'
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
                    "variables": {"input": {"topic": "FAQ output"}},
                },
            )
            assert create_resp.status_code == 200
            job_id = create_resp.json()["data"]["createJob"]
            client.post(
                "/graphql",
                json={
                    "query": "mutation($jobId: ID!) { runPipeline(jobId: $jobId) { id } }",
                    "variables": {"jobId": job_id},
                },
            )
            query_resp = client.post(
                "/graphql",
                json={
                    "query": "query($id: ID!) { job(id: $id) { articleWithFaq { sections { heading } faq { question } } } }",
                    "variables": {"id": job_id},
                },
            )
        assert query_resp.status_code == 200
        data = query_resp.json()
        assert "data" in data and data["data"]["job"] is not None
        awf = data["data"]["job"].get("articleWithFaq")
        if awf is None:
            awf = data["data"]["job"].get("article_with_faq")
        assert awf is not None
        assert "sections" in awf and len(awf["sections"]) >= 1
        assert awf["sections"][0]["heading"] == "FAQ output"
        assert "faq" in awf and len(awf["faq"]) >= 1
        assert awf["faq"][0]["question"] == "What is it?"
    finally:
        os.environ.pop("DB_PATH", None)


def test_graphql_jobs_filter_by_status():
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
            # Create two jobs (both pending)
            for topic in ["Pending A", "Pending B"]:
                client.post(
                    "/graphql",
                    json={
                        "query": "mutation($input: CreateJobInput!) { createJob(input: $input) }",
                        "variables": {"input": {"topic": topic}},
                    },
                )
            # Query for pending jobs
            resp = client.post(
                "/graphql",
                json={
                    "query": "query { jobs(status: pending) { id status topic } }",
                },
            )
        assert resp.status_code == 200
        data = resp.json()["data"]["jobs"]
        assert len(data) == 2
        assert all(j["status"] == "pending" for j in data)

        # Query for completed jobs (should be empty)
        with (
            patch("app.api.context.get_serp_client", return_value=MockSERPClient()),
            patch("app.api.context.get_llm_client", return_value=MockLLMClient()),
        ):
            resp2 = TestClient(app).post(
                "/graphql",
                json={
                    "query": "query { jobs(status: completed) { id status } }",
                },
            )
        assert resp2.status_code == 200
        assert len(resp2.json()["data"]["jobs"]) == 0
    finally:
        os.environ.pop("DB_PATH", None)


def test_graphql_retry_job_resumes_failed_job():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    os.environ["DB_PATH"] = path
    try:
        init_db(path)
        # First run: LLM returns bad JSON to fail the outline step
        bad_llm = _MultiResponseLLM(["not valid json"])
        with (
            patch("app.api.context.get_serp_client", return_value=MockSERPClient()),
            patch("app.api.context.get_llm_client", return_value=bad_llm),
        ):
            client = TestClient(app)
            create_resp = client.post(
                "/graphql",
                json={
                    "query": "mutation($input: CreateJobInput!) { createJob(input: $input) }",
                    "variables": {"input": {"topic": "Retry test"}},
                },
            )
            job_id = create_resp.json()["data"]["createJob"]
            # Run pipeline - should fail at outline step
            run_resp = client.post(
                "/graphql",
                json={
                    "query": "mutation($jobId: ID!) { runPipeline(jobId: $jobId) { id status error } }",
                    "variables": {"jobId": job_id},
                },
            )
        run_data = run_resp.json()["data"]["runPipeline"]
        assert run_data["status"] == "failed"
        assert run_data["error"] is not None

        # Second run: retry with good LLM responses
        outline = '{"sections":[{"heading_level":1,"title":"Intro","bullet_points":[]}]}'
        article = '{"sections":[{"level":1,"heading":"Retry test","content":"Content."}]}'
        metadata = (
            '{"title_tag":"T","meta_description":"D.",'
            '"primary_keyword":"Retry test","secondary_keywords":[],'
            '"internal_links":[{"anchor_text":"a","target_topic":"b"}],'
            '"external_refs":[{"url":"https://x.com","title":"X","placement_context":"c"}]}'
        )
        faq = '[{"question":"Q?","answer":"A."}]'
        good_llm = _MultiResponseLLM([outline, article, metadata, faq])
        with (
            patch("app.api.context.get_serp_client", return_value=MockSERPClient()),
            patch("app.api.context.get_llm_client", return_value=good_llm),
        ):
            retry_resp = TestClient(app).post(
                "/graphql",
                json={
                    "query": "mutation($jobId: ID!) { retryJob(jobId: $jobId) { id status error article { sections { heading } } } }",
                    "variables": {"jobId": job_id},
                },
            )
        retry_data = retry_resp.json()["data"]["retryJob"]
        assert retry_data is not None
        assert retry_data["id"] == job_id
        assert retry_data["status"] == "completed"
        assert retry_data["error"] is None
        assert retry_data["article"] is not None
    finally:
        os.environ.pop("DB_PATH", None)


def test_graphql_retry_job_nonexistent_returns_null():
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
            resp = client.post(
                "/graphql",
                json={
                    "query": "mutation($jobId: ID!) { retryJob(jobId: $jobId) { id } }",
                    "variables": {"jobId": str(uuid.uuid4())},
                },
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["retryJob"] is None
    finally:
        os.environ.pop("DB_PATH", None)
