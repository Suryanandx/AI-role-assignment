import json
import sqlite3
import uuid
from pathlib import Path

from app.models import CreateJobInput, Job, JobStatus


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            topic TEXT NOT NULL,
            word_count INTEGER NOT NULL,
            language TEXT NOT NULL,
            serp_raw TEXT,
            serp_analysis TEXT,
            outline TEXT,
            article TEXT,
            metadata TEXT,
            internal_links TEXT,
            external_refs TEXT,
            quality_score REAL,
            faq TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def _job_to_row(job: Job) -> dict:
    d = job.model_dump(mode="json")
    row = {
        "id": d["id"],
        "status": d["status"],
        "topic": d["topic"],
        "word_count": d["word_count"],
        "language": d["language"],
        "serp_raw": json.dumps(d["serp_raw"]) if d["serp_raw"] is not None else None,
        "serp_analysis": json.dumps(d["serp_analysis"]) if d["serp_analysis"] is not None else None,
        "outline": json.dumps(d["outline"]) if d["outline"] is not None else None,
        "article": json.dumps(d["article"]) if d["article"] is not None else None,
        "metadata": json.dumps(d["metadata"]) if d["metadata"] is not None else None,
        "internal_links": json.dumps(d["internal_links"]) if d.get("internal_links") is not None else None,
        "external_refs": json.dumps(d["external_refs"]) if d.get("external_refs") is not None else None,
        "quality_score": d["quality_score"],
        "faq": json.dumps(d["faq"]) if d["faq"] is not None else None,
        "error": d["error"],
        "created_at": d["created_at"],
        "updated_at": d["updated_at"],
    }
    return row


def _row_to_job(row: sqlite3.Row) -> Job:
    d = {
        "id": row["id"],
        "status": row["status"],
        "topic": row["topic"],
        "word_count": row["word_count"],
        "language": row["language"],
        "serp_raw": json.loads(row["serp_raw"]) if row["serp_raw"] else None,
        "serp_analysis": json.loads(row["serp_analysis"]) if row["serp_analysis"] else None,
        "outline": json.loads(row["outline"]) if row["outline"] else None,
        "article": json.loads(row["article"]) if row["article"] else None,
        "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        "internal_links": json.loads(row["internal_links"]) if row["internal_links"] else [],
        "external_refs": json.loads(row["external_refs"]) if row["external_refs"] else [],
        "quality_score": row["quality_score"],
        "faq": json.loads(row["faq"]) if row["faq"] else None,
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    return Job.model_validate(d)


def create_job(db_path: str, input: CreateJobInput) -> Job:
    init_db(db_path)
    job = Job(
        status=JobStatus.pending,
        topic=input.topic,
        word_count=input.word_count,
        language=input.language,
    )
    row = _job_to_row(job)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        INSERT INTO jobs (
            id, status, topic, word_count, language,
            serp_raw, serp_analysis, outline, article, metadata,
            internal_links, external_refs, quality_score, faq, error,
            created_at, updated_at
        ) VALUES (
            :id, :status, :topic, :word_count, :language,
            :serp_raw, :serp_analysis, :outline, :article, :metadata,
            :internal_links, :external_refs, :quality_score, :faq, :error,
            :created_at, :updated_at
        )
        """,
        row,
    )
    conn.commit()
    conn.close()
    return job


def get_job(db_path: str, job_id: uuid.UUID | str) -> Job | None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    sid = str(job_id) if isinstance(job_id, uuid.UUID) else job_id
    cur = conn.execute("SELECT * FROM jobs WHERE id = ?", (sid,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_job(row)


_UPDATABLE = {
    "status", "serp_raw", "serp_analysis", "outline", "article", "metadata",
    "internal_links", "external_refs", "quality_score", "faq", "error", "updated_at",
}
_JSON_COLUMNS = {
    "serp_raw", "serp_analysis", "outline", "article", "metadata",
    "internal_links", "external_refs", "faq",
}


def update_job(db_path: str, job_id: uuid.UUID | str, updates: dict) -> Job | None:
    from datetime import datetime, timezone

    sid = str(job_id) if isinstance(job_id, uuid.UUID) else job_id
    updates = {k: v for k, v in updates.items() if k in _UPDATABLE}
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    set_parts = []
    values = []
    for k, v in updates.items():
        if k in _JSON_COLUMNS and v is not None and not isinstance(v, str):
            v = json.dumps(v)
        set_parts.append(f"{k} = ?")
        values.append(v)
    if not set_parts:
        return get_job(db_path, job_id)
    values.append(sid)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE jobs SET " + ", ".join(set_parts) + " WHERE id = ?",
        values,
    )
    updated = conn.total_changes
    conn.commit()
    conn.close()
    if updated == 0:
        return None
    return get_job(db_path, job_id)
