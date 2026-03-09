#!/usr/bin/env python3
"""Run a full pipeline with Ollama: create job, run pipeline, poll until done, print result."""

import os
import sys
import time

import httpx

GRAPHQL_URL = os.environ.get("GRAPHQL_URL", "http://localhost:8000/graphql")
POLL_INTERVAL = 5
MAX_WAIT = 600  # 10 minutes


def graphql(query: str, variables: dict | None = None) -> dict:
    resp = httpx.post(GRAPHQL_URL, json={"query": query, "variables": variables or {}}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data.get("data", {})


def main():
    topic = sys.argv[1] if len(sys.argv) > 1 else "best productivity tools for remote teams"
    print(f"Creating job for topic: {topic}")
    data = graphql(
        "mutation($input: CreateJobInput!) { createJob(input: $input) }",
        {"input": {"topic": topic, "wordCount": 500, "language": "en"}},
    )
    job_id = data["createJob"]
    print(f"Job ID: {job_id}")

    print("Running pipeline (Ollama)...")
    try:
        graphql(
            "mutation($jobId: ID!) { runPipeline(jobId: $jobId) { id status } }",
            {"jobId": job_id},
        )
    except Exception as e:
        print(f"runPipeline request failed (backend may still be processing): {e}")

    query = """
    query($id: ID!) {
      job(id: $id) {
        id status error
        topic
        article { sections { level heading content } }
        metadata { titleTag metaDescription primaryKeyword }
        faq { question answer }
      }
    }
    """
    start = time.monotonic()
    while time.monotonic() - start < MAX_WAIT:
        data = graphql(query, {"id": job_id})
        job = data.get("job")
        if not job:
            print("Job not found")
            return 1
        status = job["status"]
        print(f"  Status: {status}")
        if status == "completed":
            print("\n--- Pipeline completed ---")
            if job.get("metadata"):
                m = job["metadata"]
                print(f"Title: {m.get('titleTag', '')}")
                print(f"Meta: {(m.get('metaDescription') or '')[:80]}...")
            if job.get("article", {}).get("sections"):
                for s in job["article"]["sections"][:3]:
                    print(f"\nH{s.get('level', 1)}: {s.get('heading', '')}")
                    print((s.get("content") or "")[:200] + ("..." if len(s.get("content") or "") > 200 else ""))
            if job.get("faq"):
                print("\nFAQ:")
                for f in job["faq"][:3]:
                    print(f"  Q: {f.get('question', '')}")
                    print(f"  A: {f.get('answer', '')[:80]}...")
            return 0
        if status == "failed":
            print(f"\nPipeline failed: {job.get('error', 'unknown')}")
            return 1
        time.sleep(POLL_INTERVAL)

    print("Timeout waiting for completion")
    return 1


if __name__ == "__main__":
    sys.exit(main())
