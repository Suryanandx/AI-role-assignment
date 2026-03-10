#!/usr/bin/env python3
"""Lightweight E2E verification: health, create job, list jobs, get job. No pipeline run."""

import os
import sys

import httpx

BASE = os.environ.get("BACKEND_URL", "http://localhost:8000")
GRAPHQL = f"{BASE.rstrip('/')}/graphql"


def main():
    errors = []
    with httpx.Client(timeout=10.0) as client:
        # Health
        try:
            r = client.get(f"{BASE}/health")
            assert r.status_code == 200, r.text
            assert "ok" in r.json().get("status", "")
            print("  GET /health OK")
        except Exception as e:
            errors.append(f"health: {e}")
            print(f"  GET /health FAIL: {e}")
            return 1

        # Create job
        try:
            r = client.post(
                GRAPHQL,
                json={
                    "query": "mutation($input: CreateJobInput!) { createJob(input: $input) }",
                    "variables": {"input": {"topic": "E2E verify", "wordCount": 500, "language": "en"}},
                },
            )
            r.raise_for_status()
            data = r.json()
            if data.get("errors"):
                raise RuntimeError(data["errors"])
            job_id = data["data"]["createJob"]
            assert job_id and len(job_id) > 10
            print(f"  createJob OK (id={job_id[:8]}...)")
        except Exception as e:
            errors.append(f"createJob: {e}")
            print(f"  createJob FAIL: {e}")
            return 1

        # List jobs
        try:
            r = client.post(
                GRAPHQL,
                json={
                    "query": "query { jobs(limit: 5) { id status topic createdAt } }",
                },
            )
            r.raise_for_status()
            data = r.json()
            if data.get("errors"):
                raise RuntimeError(data["errors"])
            jobs = data["data"].get("jobs") or []
            assert isinstance(jobs, list)
            found = any(j.get("id") == job_id for j in jobs)
            print(f"  jobs(limit=5) OK (count={len(jobs)}, new job in list={found})")
        except Exception as e:
            errors.append(f"jobs: {e}")
            print(f"  jobs list FAIL: {e}")
            return 1

        # Get job
        try:
            r = client.post(
                GRAPHQL,
                json={
                    "query": "query($id: ID!) { job(id: $id) { id status topic } }",
                    "variables": {"id": job_id},
                },
            )
            r.raise_for_status()
            data = r.json()
            if data.get("errors"):
                raise RuntimeError(data["errors"])
            job = data["data"].get("job")
            assert job and job["id"] == job_id and job["topic"] == "E2E verify"
            print(f"  job(id) OK (status={job['status']})")
        except Exception as e:
            errors.append(f"job: {e}")
            print(f"  job(id) FAIL: {e}")
            return 1

    print("E2E verify passed.")
    return 0


if __name__ == "__main__":
    print("E2E verify (health, create, list, get)...")
    sys.exit(main())
