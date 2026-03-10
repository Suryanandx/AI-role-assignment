import tempfile
import uuid

from app.db import get_job, init_db
from app.models import CreateJobInput, JobStatus
from app.models import Job, JobStatus
from app.models.serp import SERPAnalysis
from app.pipeline import (
    create_job_step,
    run_article_step,
    run_faq_step,
    run_metadata_step,
    run_outline_step,
    run_pipeline,
    run_revision_step,
    run_serp_step,
    run_validation_step,
)
from app.pipeline.steps import _build_faq_messages
from app.services import MockLLMClient, MockSERPClient


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


def test_run_outline_step_success():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(
        CreateJobInput(topic="SEO tips", word_count=1500, language="en"),
        path,
    )
    run_serp_step(job_id, path, MockSERPClient())
    mock_json = '{"sections":[{"heading_level":1,"title":"Intro","bullet_points":["p1"]}]}'
    job = run_outline_step(job_id, path, MockLLMClient(response=mock_json))
    assert job is not None
    assert job.outline is not None
    assert len(job.outline.sections) == 1
    assert job.outline.sections[0].heading_level == 1
    assert job.outline.sections[0].title == "Intro"
    assert job.outline.sections[0].bullet_points == ["p1"]
    assert job.error is None


def test_run_outline_step_unknown_job_returns_none():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    result = run_outline_step(uuid.uuid4(), path, MockLLMClient())
    assert result is None


def test_run_outline_step_invalid_json_sets_error():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    job = run_outline_step(job_id, path, MockLLMClient(response="not valid json"))
    assert job is not None
    assert job.outline is None
    assert job.error is not None
    assert "Outline generation failed" in job.error
    assert "invalid JSON" in job.error or "JSON" in job.error


def test_run_outline_step_invalid_schema_sets_error():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    job = run_outline_step(
        job_id,
        path,
        MockLLMClient(response='{"sections":[{"heading_level":99,"title":"Bad","bullet_points":[]}]}'),
    )
    assert job is not None
    assert job.outline is None
    assert job.error is not None
    assert "Outline generation failed" in job.error


def test_run_article_step_success():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(
        CreateJobInput(topic="SEO tips", word_count=1500, language="en"),
        path,
    )
    run_serp_step(job_id, path, MockSERPClient())
    outline_json = '{"sections":[{"heading_level":1,"title":"Intro","bullet_points":["p1"]}]}'
    run_outline_step(job_id, path, MockLLMClient(response=outline_json))
    article_json = '{"sections":[{"level":1,"heading":"Intro","content":"First para."}]}'
    job = run_article_step(job_id, path, MockLLMClient(response=article_json))
    assert job is not None
    assert job.article is not None
    assert len(job.article.sections) == 1
    assert job.article.sections[0].level == 1
    assert job.article.sections[0].heading == "Intro"
    assert job.article.sections[0].content == "First para."
    assert job.error is None


def test_run_article_step_unknown_job_returns_none():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    result = run_article_step(uuid.uuid4(), path, MockLLMClient())
    assert result is None


def test_run_article_step_no_outline_sets_error():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    job = run_article_step(job_id, path, MockLLMClient(response='{"sections":[]}'))
    assert job is not None
    assert job.article is None
    assert job.error is not None
    assert "no outline" in job.error


def test_run_article_step_invalid_json_sets_error():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    outline_json = '{"sections":[{"heading_level":1,"title":"Intro","bullet_points":[]}]}'
    run_outline_step(job_id, path, MockLLMClient(response=outline_json))
    job = run_article_step(job_id, path, MockLLMClient(response="not json"))
    assert job is not None
    assert job.article is None
    assert job.error is not None
    assert "Article generation failed" in job.error


def test_run_article_step_invalid_schema_sets_error():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    outline_json = '{"sections":[{"heading_level":1,"title":"Intro","bullet_points":[]}]}'
    run_outline_step(job_id, path, MockLLMClient(response=outline_json))
    job = run_article_step(
        job_id,
        path,
        MockLLMClient(response='{"sections":[{"level":99,"heading":"Bad","content":"x"}]}'),
    )
    assert job is not None
    assert job.article is None
    assert job.error is not None
    assert "Article generation failed" in job.error


def _run_serp_outline_article(path, job_id):
    run_serp_step(job_id, path, MockSERPClient())
    run_outline_step(
        job_id,
        path,
        MockLLMClient(response='{"sections":[{"heading_level":1,"title":"Intro","bullet_points":[]}]}'),
    )
    run_article_step(
        job_id,
        path,
        MockLLMClient(response='{"sections":[{"level":1,"heading":"Intro","content":"First para."}]}'),
    )


def test_run_metadata_step_success():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="SEO tips", word_count=1500, language="en"), path)
    _run_serp_outline_article(path, job_id)
    metadata_json = (
        '{"title_tag":"SEO Tips Guide","meta_description":"Learn SEO tips for your site. Read our guide.",'
        '"primary_keyword":"SEO tips","secondary_keywords":["keywords","content"],'
        '"internal_links":[{"anchor_text":"keyword research","target_topic":"research"},'
        '{"anchor_text":"content","target_topic":"content strategy"}],'
        '"external_refs":[{"url":"https://example.com/1","title":"Source 1","placement_context":"intro"}]}'
    )
    job = run_metadata_step(job_id, path, MockLLMClient(response=metadata_json))
    assert job is not None
    assert job.metadata is not None
    assert job.metadata.title_tag == "SEO Tips Guide"
    assert len(job.metadata.title_tag) <= 60
    assert 0 < len(job.metadata.meta_description) <= 160
    assert job.metadata.primary_keyword == "SEO tips"
    assert len(job.internal_links) >= 1 and len(job.internal_links) <= 5
    assert len(job.external_refs) >= 1 and len(job.external_refs) <= 4
    assert job.error is None


def test_run_metadata_step_unknown_job_returns_none():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    result = run_metadata_step(uuid.uuid4(), path, MockLLMClient())
    assert result is None


def test_run_metadata_step_no_article_sets_error():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    job = run_metadata_step(job_id, path, MockLLMClient(response="{}"))
    assert job is not None
    assert job.error is not None
    assert "no article" in job.error


def test_run_metadata_step_invalid_json_sets_error():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    _run_serp_outline_article(path, job_id)
    job = run_metadata_step(job_id, path, MockLLMClient(response="not json"))
    assert job is not None
    assert job.error is not None
    assert "Metadata step failed" in job.error


def test_run_metadata_step_invalid_schema_sets_error():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    _run_serp_outline_article(path, job_id)
    invalid_json = (
        '{"title_tag":"X","meta_description":"Desc.","primary_keyword":"x","secondary_keywords":[],'
        '"internal_links":[{"anchor_text":"ok","target_topic":"t"},{"target_topic":"missing_anchor"}],'
        '"external_refs":[{"url":"https://x.com","title":"X","placement_context":"intro"}]}'
    )
    job = run_metadata_step(job_id, path, MockLLMClient(response=invalid_json))
    assert job is not None
    assert job.error is not None
    assert "Metadata step failed" in job.error


def test_run_validation_step_success_high_score():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="SEO tips", word_count=1500, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    run_outline_step(
        job_id,
        path,
        MockLLMClient(response='{"sections":[{"heading_level":1,"title":"Intro","bullet_points":[]}]}'),
    )
    article_json = (
        '{"sections":[{"level":1,"heading":"SEO tips for beginners","content":"SEO tips help your site rank. Start here."}]}'
    )
    run_article_step(job_id, path, MockLLMClient(response=article_json))
    metadata_json = (
        '{"title_tag":"SEO Tips Guide - 50 chars here exactly right",'
        '"meta_description":"Learn SEO tips for your site. Read our guide and improve rankings today. More text here.",'
        '"primary_keyword":"SEO tips","secondary_keywords":["keywords"],'
        '"internal_links":'
        '[{"anchor_text":"a","target_topic":"t1"},{"anchor_text":"b","target_topic":"t2"},{"anchor_text":"c","target_topic":"t3"},{"anchor_text":"d","target_topic":"t4"}],'
        '"external_refs":[{"url":"https://a.com","title":"A","placement_context":"intro"},'
        '{"url":"https://b.com","title":"B","placement_context":"body"},{"url":"https://c.com","title":"C","placement_context":"end"}]}'
    )
    run_metadata_step(job_id, path, MockLLMClient(response=metadata_json))
    job = run_validation_step(job_id, path)
    assert job is not None
    assert job.quality_score is not None
    assert 0 <= job.quality_score <= 1
    assert job.quality_score >= 0.7
    assert job.error is None


def test_run_validation_step_unknown_job_returns_none():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    result = run_validation_step(uuid.uuid4(), path)
    assert result is None


def test_run_validation_step_no_article_sets_error():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    job = run_validation_step(job_id, path)
    assert job is not None
    assert job.error is not None
    assert "no article" in job.error
    assert job.quality_score is None


def test_run_validation_step_low_score_when_data_missing():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    _run_serp_outline_article(path, job_id)
    job = run_validation_step(job_id, path)
    assert job is not None
    assert job.quality_score is not None
    assert 0 <= job.quality_score <= 1
    assert job.quality_score < 0.6


def test_run_validation_step_keyword_in_h1_and_intro_reflects_in_score():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="productivity", word_count=1500, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    run_outline_step(
        job_id,
        path,
        MockLLMClient(response='{"sections":[{"heading_level":1,"title":"Intro","bullet_points":[]}]}'),
    )
    article_json = (
        '{"sections":[{"level":1,"heading":"Productivity tips","content":"Boost productivity with these steps."}]}'
    )
    run_article_step(job_id, path, MockLLMClient(response=article_json))
    job = run_validation_step(job_id, path)
    assert job is not None
    assert job.quality_score is not None
    assert job.quality_score >= 0.25


class _MultiResponseLLM:
    """Mock LLM that returns the next response from a list on each generate() call."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    def generate(self, messages, *, options=None):
        if not self._responses:
            return "{}"
        return self._responses.pop(0)


def test_run_pipeline_full_run_to_completion():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="SEO guide", word_count=1500, language="en"), path)
    outline_json = '{"sections":[{"heading_level":1,"title":"Intro","bullet_points":[]}]}'
    article_json = '{"sections":[{"level":1,"heading":"SEO guide","content":"This is the intro."}]}'
    metadata_json = (
        '{"title_tag":"SEO Guide","meta_description":"Learn SEO. Read more.",'
        '"primary_keyword":"SEO guide","secondary_keywords":[],'
        '"internal_links":[{"anchor_text":"a","target_topic":"t1"},{"anchor_text":"b","target_topic":"t2"}],'
        '"external_refs":[{"url":"https://x.com","title":"X","placement_context":"intro"}]}'
    )
    faq_json = '[{"question":"What is SEO?","answer":"SEO is search engine optimization."},{"question":"Why use it?","answer":"To rank better."}]'
    llm = _MultiResponseLLM([outline_json, article_json, metadata_json, faq_json])
    job = run_pipeline(job_id, path, MockSERPClient(), llm)
    assert job is not None
    assert job.status == JobStatus.completed
    assert job.serp_analysis is not None
    assert job.outline is not None
    assert job.article is not None
    assert job.metadata is not None
    assert job.faq is not None
    assert len(job.faq) == 2
    assert job.faq[0].question == "What is SEO?" and job.faq[0].answer
    assert job.quality_score is not None
    assert job.error is None


def test_run_pipeline_unknown_job_returns_none():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    result = run_pipeline(uuid.uuid4(), path, MockSERPClient(), MockLLMClient())
    assert result is None


def test_run_pipeline_resume_skips_completed_steps():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="Resume topic", word_count=1000, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    job_before = get_job(path, job_id)
    assert job_before is not None
    serp_themes = job_before.serp_analysis.themes if job_before.serp_analysis else []

    outline_json = '{"sections":[{"heading_level":1,"title":"Resume","bullet_points":[]}]}'
    article_json = '{"sections":[{"level":1,"heading":"Resume","content":"Content."}]}'
    metadata_json = (
        '{"title_tag":"Resume","meta_description":"Resume guide.",'
        '"primary_keyword":"Resume topic","secondary_keywords":[],'
        '"internal_links":[{"anchor_text":"x","target_topic":"y"}],'
        '"external_refs":[{"url":"https://a.com","title":"A","placement_context":"body"}]}'
    )
    faq_json = '[{"question":"Q?","answer":"A."}]'
    llm = _MultiResponseLLM([outline_json, article_json, metadata_json, faq_json])
    job = run_pipeline(job_id, path, MockSERPClient(), llm)
    assert job is not None
    assert job.status == JobStatus.completed
    assert job.serp_analysis is not None
    assert job.serp_analysis.themes == serp_themes
    assert job.outline is not None
    assert job.article is not None
    assert job.metadata is not None
    assert job.faq is not None
    assert job.quality_score is not None


def test_run_pipeline_failure_sets_status_failed():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="Fail topic", word_count=1000, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    llm = _MultiResponseLLM(["not valid json"])
    job = run_pipeline(job_id, path, MockSERPClient(), llm)
    assert job is not None
    assert job.status == JobStatus.failed
    assert job.error is not None


def test_run_faq_step_success():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="FAQ topic", word_count=1000, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    run_outline_step(
        job_id,
        path,
        MockLLMClient(response='{"sections":[{"heading_level":1,"title":"Intro","bullet_points":[]}]}'),
    )
    run_article_step(
        job_id,
        path,
        MockLLMClient(response='{"sections":[{"level":1,"heading":"FAQ topic","content":"Some content."}]}'),
    )
    faq_json = '[{"question":"What is it?","answer":"An answer."},{"question":"How?","answer":"Like this."}]'
    job = run_faq_step(job_id, path, MockLLMClient(response=faq_json))
    assert job is not None
    assert job.faq is not None
    assert len(job.faq) == 2
    assert job.faq[0].question == "What is it?" and job.faq[0].answer == "An answer."
    assert job.faq[1].question == "How?" and job.faq[1].answer == "Like this."
    assert job.error is None


def test_run_faq_step_unknown_job_returns_none():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    result = run_faq_step(uuid.uuid4(), path, MockLLMClient())
    assert result is None


def test_run_faq_step_no_serp_or_article_sets_error():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    job = run_faq_step(job_id, path, MockLLMClient(response="[]"))
    assert job is not None
    assert job.error is not None
    assert "no SERP analysis or article" in job.error


def test_run_faq_step_invalid_json_sets_error():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    job = run_faq_step(job_id, path, MockLLMClient(response="not json"))
    assert job is not None
    assert job.error is not None
    assert "FAQ step failed" in job.error


def test_run_faq_step_invalid_schema_sets_error():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    job = run_faq_step(job_id, path, MockLLMClient(response='[{"question":"Q?","answer":"A."},{"wrong":"shape"}]'))
    assert job is not None
    assert job.error is not None
    assert "FAQ step failed" in job.error


def test_faq_step_paa_questions_included_in_prompt():
    job = Job(
        status=JobStatus.pending,
        topic="PAA topic",
        word_count=1000,
        language="en",
        serp_analysis=SERPAnalysis(paa_questions=["What is X?", "How to Y?"]),
    )
    messages = _build_faq_messages(job)
    assert len(messages) >= 2
    user_content = next((m["content"] for m in messages if m.get("role") == "user"), "")
    assert "What is X?" in user_content
    assert "How to Y?" in user_content


def test_run_revision_step_success():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="Rev", word_count=1000, language="en"), path)
    _run_serp_outline_article(path, job_id)
    revised_json = (
        '{"sections":[{"level":1,"heading":"Revised intro","content":"Revised content with keyword."},'
        '{"level":2,"heading":"Section two","content":"Body."}]}'
    )
    job = run_revision_step(job_id, path, MockLLMClient(response=revised_json), "improve intro for keyword density")
    assert job is not None
    assert job.article is not None
    assert len(job.article.sections) == 2
    assert job.article.sections[0].heading == "Revised intro"
    assert job.error is None


def test_run_revision_step_unknown_job_returns_none():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    result = run_revision_step(uuid.uuid4(), path, MockLLMClient(), "improve intro")
    assert result is None


def test_run_revision_step_no_article_sets_error():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    job = run_revision_step(job_id, path, MockLLMClient(), "improve intro")
    assert job is not None
    assert job.error is not None
    assert "no article" in job.error


def test_run_revision_step_invalid_json_sets_error():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    _run_serp_outline_article(path, job_id)
    job = run_revision_step(job_id, path, MockLLMClient(response="not json"), "improve intro")
    assert job is not None
    assert job.error is not None
    assert "Revision step failed" in job.error


def test_run_revision_step_invalid_schema_sets_error():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="x", word_count=1000, language="en"), path)
    _run_serp_outline_article(path, job_id)
    job = run_revision_step(job_id, path, MockLLMClient(response='{"wrong":"shape"}'), "improve intro")
    assert job is not None
    assert job.error is not None
    assert "Revision step failed" in job.error


def test_quality_scorer_sentence_variety_and_heading_order():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="Keyword", word_count=1500, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    run_outline_step(
        job_id,
        path,
        MockLLMClient(response='{"sections":[{"heading_level":1,"title":"Intro","bullet_points":[]}]}'),
    )
    article_good = (
        '{"sections":['
        '{"level":1,"heading":"Keyword guide","content":"Keyword matters for SEO. This is a longer second sentence with more words for variety."},'
        '{"level":2,"heading":"Details","content":"Section two."}'
        ']}'
    )
    run_article_step(job_id, path, MockLLMClient(response=article_good))
    metadata_json = (
        '{"title_tag":"Keyword Guide","meta_description":"Learn about keyword. More text here to hit length.",'
        '"primary_keyword":"Keyword","secondary_keywords":[],'
        '"internal_links":[{"anchor_text":"a","target_topic":"b"},{"anchor_text":"c","target_topic":"d"},{"anchor_text":"e","target_topic":"f"}],'
        '"external_refs":[{"url":"https://x.com","title":"X","placement_context":"intro"},{"url":"https://y.com","title":"Y","placement_context":"body"}]}'
    )
    run_metadata_step(job_id, path, MockLLMClient(response=metadata_json))
    job = run_validation_step(job_id, path)
    assert job is not None
    assert job.quality_score is not None
    assert 0 <= job.quality_score <= 1
    assert job.quality_score >= 0.6


def test_quality_scorer_bad_heading_order_lower_score():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="Topic", word_count=1500, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    run_outline_step(
        job_id,
        path,
        MockLLMClient(response='{"sections":[{"heading_level":1,"title":"Intro","bullet_points":[]}]}'),
    )
    article_bad_order = (
        '{"sections":['
        '{"level":2,"heading":"Wrong first","content":"H2 first."},'
        '{"level":1,"heading":"Topic","content":"Topic is here."}'
        ']}'
    )
    run_article_step(job_id, path, MockLLMClient(response=article_bad_order))
    job = run_validation_step(job_id, path)
    assert job is not None
    assert job.quality_score is not None
    assert 0 <= job.quality_score <= 1


def test_run_pipeline_sets_current_step_to_none_on_completion():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="Step test", word_count=1500, language="en"), path)
    outline_json = '{"sections":[{"heading_level":1,"title":"Intro","bullet_points":[]}]}'
    article_json = '{"sections":[{"level":1,"heading":"Step test","content":"Content."}]}'
    metadata_json = (
        '{"title_tag":"Step","meta_description":"Step guide.",'
        '"primary_keyword":"Step test","secondary_keywords":[],'
        '"internal_links":[{"anchor_text":"a","target_topic":"b"}],'
        '"external_refs":[{"url":"https://x.com","title":"X","placement_context":"c"}]}'
    )
    faq_json = '[{"question":"Q?","answer":"A."}]'
    llm = _MultiResponseLLM([outline_json, article_json, metadata_json, faq_json])
    job = run_pipeline(job_id, path, MockSERPClient(), llm)
    assert job is not None
    assert job.status == JobStatus.completed
    assert job.current_step is None


def test_run_pipeline_sets_current_step_to_none_on_failure():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="Fail step", word_count=1000, language="en"), path)
    run_serp_step(job_id, path, MockSERPClient())
    llm = _MultiResponseLLM(["not valid json"])
    job = run_pipeline(job_id, path, MockSERPClient(), llm)
    assert job is not None
    assert job.status == JobStatus.failed
    assert job.current_step is None


def test_run_pipeline_triggers_revision_when_below_threshold():
    import os

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    job_id = create_job_step(CreateJobInput(topic="LowScore", word_count=1000, language="en"), path)
    outline_json = '{"sections":[{"heading_level":1,"title":"Intro","bullet_points":[]}]}'
    article_json = '{"sections":[{"level":1,"heading":"Other","content":"No keyword here."}]}'
    metadata_json = (
        '{"title_tag":"T","meta_description":"D.",'
        '"primary_keyword":"LowScore","secondary_keywords":[],'
        '"internal_links":[{"anchor_text":"a","target_topic":"b"}],'
        '"external_refs":[{"url":"https://x.com","title":"X","placement_context":"c"}]}'
    )
    revised_json = '{"sections":[{"level":1,"heading":"LowScore guide","content":"LowScore is important."}]}'
    faq_json = '[{"question":"Q?","answer":"A."}]'
    llm = _MultiResponseLLM([outline_json, article_json, metadata_json, faq_json, revised_json])
    os.environ["QUALITY_SCORE_THRESHOLD"] = "0.99"
    try:
        job = run_pipeline(job_id, path, MockSERPClient(), llm)
    finally:
        os.environ.pop("QUALITY_SCORE_THRESHOLD", None)
    assert job is not None
    assert job.quality_score is not None
    assert job.status in (JobStatus.completed, JobStatus.failed)
