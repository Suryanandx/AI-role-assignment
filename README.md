# SEO Article Generator

Backend service that generates SEO-optimized articles from a topic: SERP research, outline, article writing, metadata, and validation. Built for the AISEO Backend Engineer take-home.

**Design document:** [SEO Article Generator Design Document](https://docs.google.com/document/d/1Jw-C8bzjgTT0HzGL2XNyLeXwPjk6QcCZDGmgmRaR4v0/edit?usp=sharing)

**Author:** [Suryanand](https://github.com/suryanandx) | GitHub: [suryanandx](https://github.com/suryanandx) | Email: [work@suryanand.com](mailto:work@suryanand.com)

---

## How to run

**Requirements:** Python 3.11+

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Server runs at `http://localhost:8000`. Health: `GET /health` returns `{"status": "ok"}`. Optional: `GET /ready` pings Ollama and returns `{"ready": true, "ollama": "ok"}` or `{"ready": false, "ollama": "unreachable"}`.

**Frontend (Next.js):**

```bash
cd frontend
cp .env.local.example .env.local   # optional; defaults to http://localhost:8000/graphql
npm install
npm run dev
```

App runs at `http://localhost:3000`. Use the job lookup page to query a job by ID (backend must be running).

**Docker (backend, frontend, Ollama, DB):**

Ensure Docker is running, then:

```bash
docker compose up --build
```

- Backend: http://localhost:8000 (health: `GET /health`). The backend service has a healthcheck; the table is created automatically on startup via `init_db` (no manual migrations).
- Frontend: http://localhost:3000
- Ollama: http://localhost:11434 (real LLM; pipeline uses it when you run a job). Optional healthcheck; ensure the model is pulled before running jobs.

SQLite is stored in volume `backend_data` at `/data/jobs.db`; the DB and table are created automatically on first startup. Ollama models live in `ollama_data`. Pull the default model before running a job (first time or after clearing volumes):

```bash
docker compose exec ollama ollama pull llama3
```

Backend in Docker uses `OLLAMA_BASE_URL=http://ollama:11434` and `DB_PATH=/data/jobs.db`. SERP is mock by default (`SERP_USE_MOCK=true`). For real SERP in Docker, set `SERP_USE_MOCK=false` and `SERPAPI_KEY` in the backend service environment.

**Optional env:** Create `backend/.env` with:

| Variable        | Default                     | Description              |
|----------------|-----------------------------|--------------------------|
| OLLAMA_BASE_URL | http://localhost:11434     | Ollama API base URL (use `http://ollama:11434` in Docker) |
| OLLAMA_MODEL   | llama3                      | Model name               |
| SERP_USE_MOCK  | true                        | Use mock SERP data; set to false to use a real provider |
| SERP_PROVIDER  | serpapi                     | Real SERP provider when mock is off (only `serpapi` supported) |
| SERPAPI_KEY    | (none)                      | SerpAPI key; required when SERP_USE_MOCK=false |
| DB_PATH        | ./data/jobs.db              | SQLite path (`/data/jobs.db` in Docker) |

With `SERP_USE_MOCK=false`, set `SERPAPI_KEY` to a valid SerpAPI key or the pipeline will raise at startup. See `backend/.env.example` for a template.

**Demo script (full pipeline with Ollama):** With the backend and Ollama running (and a model pulled, e.g. `ollama pull llama3`):

```bash
cd backend && python scripts/run_demo.py "best productivity tools for remote teams"
```

Creates a job, runs the pipeline, polls until completed or failed, then prints the article summary and FAQ.

**E2E verification:** (1) Start backend and Ollama (or `docker compose up`). (2) Pull model: `ollama pull llama3` (or `docker compose exec ollama ollama pull llama3`). (3) Create a job (UI or `run_demo.py`). (4) Run pipeline and wait for completion. (5) Open the job in the UI: status "completed", article sections, metadata, FAQ, internal/external links. (6) On the home page, confirm "Recent jobs" lists the job and "View" opens the job page.

Quick API check (no pipeline): from repo root with backend running, `cd backend && python scripts/e2e_verify.py`. Checks health, createJob, jobs list, and job(id).

---

## Project structure

```
backend/          # FastAPI, GraphQL at /graphql
  app/
    api/          # GraphQL and HTTP routes
    models/       # Pydantic models
    pipeline/     # SERP, outline, article, validation
    services/     # LLM, SERP clients
    config.py     # Settings from env
    main.py       # FastAPI app, health route
  tests/
  requirements.txt
frontend/         # Next.js app; GraphQL client, job lookup page
  app/            # App Router pages
  lib/            # GraphQL client
```

GraphQL at `/graphql` exposes `job(id)` and `jobs(limit, offset)` for fetching a single job or listing recent jobs (newest first). All pipeline outputs (article, SEO metadata, FAQ, internal links, external refs, quality score) are saved to the SQLite DB at each step; a completed job returned by `job(id)` includes the full saved data.

---

## Example: input and output

**Input** (e.g. via `createJob` then `runPipeline`, or the demo script):

- **Topic:** `best productivity tools for remote teams`
- **Word count:** 1500
- **Language:** en

**Output** (abbreviated shape of `job(id)` when status is `completed`):

```json
{
  "id": "<uuid>",
  "status": "completed",
  "topic": "best productivity tools for remote teams",
  "metadata": {
    "titleTag": "Best Productivity Tools for Remote Teams in 2024",
    "metaDescription": "Discover the top productivity tools for remote teams. Compare features, pricing, and integrations to boost your distributed team's output.",
    "primaryKeyword": "productivity tools for remote teams"
  },
  "article": {
    "sections": [
      { "level": 1, "heading": "Best Productivity Tools for Remote Teams", "content": "Remote work has made team productivity tools essential. This guide covers the top options..." },
      { "level": 2, "heading": "What to Look for in Remote Team Tools", "content": "Key features include real-time collaboration, task tracking, and integrations..." }
    ]
  },
  "faq": [
    { "question": "What are the best productivity tools for remote teams?", "answer": "Popular choices include tools for chat, project management, and document collaboration." },
    { "question": "How do remote team tools improve productivity?", "answer": "They centralize communication, automate workflows, and keep tasks visible." }
  ],
  "internalLinks": [
    { "anchorText": "remote work setup", "targetTopic": "home office setup guide" },
    { "anchorText": "async communication", "targetTopic": "async vs sync communication" }
  ],
  "externalRefs": [
    { "url": "https://example.com/remote-tools", "title": "Remote Work Tools Report", "placementContext": "intro" }
  ],
  "qualityScore": 0.82
}
```

Run `python scripts/run_demo.py "best productivity tools for remote teams"` to produce a real completed job and see the full output.

---

## Tech stack

- **API:** FastAPI
- **Config:** pydantic-settings
- **GraphQL:** Strawberry (planned)
- **LLM:** Ollama (OpenAI-compatible)
- **DB:** SQLite
- **Tests:** pytest, pytest-asyncio

---

## Tests

From `backend/`:

```bash
source .venv/bin/activate
pytest tests/ -v
```

---

## Design decisions

- **GraphQL:** Single endpoint at `/graphql` with flexible queries (`job(id)`, `jobs(limit, offset)`). Fits the nested shape of a job (article, metadata, FAQ, links) and keeps the frontend to one API.
- **SQLite:** One-table persistence with `init_db` on startup; no separate DB server. Sufficient for the take-home and keeps local/Docker setup simple.
- **Ollama:** Local LLM with an OpenAI-compatible API. The pipeline uses it for outline, article, metadata, FAQ, and optional revision; no API keys for development.
- **Persist every step:** Each pipeline step writes its result to the DB. Jobs survive restarts and can resume from the last completed step; the frontend and API always read the current state from the DB.

---

## Original assignment brief

*Context for the take-home assessment.*

### Context

We're building a content generation platform that helps businesses create SEO-optimized articles at scale. One of our core features is an intelligent agent that can analyze search engine results and produce high-quality, keyword-optimized content that ranks well while still reading naturally.

### The problem

Design and implement a backend service that generates SEO-optimized articles for a given topic. The system should be intelligent about how it approaches content creation: not just generating text, but understanding what's ranking on search engines and why.

### What we're looking for

Build an agent-based system that takes a topic (e.g. "best productivity tools for remote teams") and produces a complete, publish-ready article. The agent should:

1. Research the competitive landscape by analyzing the top 10 search results for relevant keywords
2. Identify what topics and subtopics are being covered by successful content
3. Generate a structured outline that addresses the same search intent
4. Produce a full article that follows SEO best practices without feeling robotic

### Technical requirements

**Input:** Topic or primary keyword, target word count (default 1500), language preference.

**Output:** Article with H1/H2/H3 hierarchy, SEO metadata (title tag, meta description), keyword analysis, structured data, 3–5 internal link suggestions, 2–4 external references with placement context.

**Architecture:** Structured data models (Pydantic or similar), graceful handling of external API failures, persist jobs for tracking and resume, validate output against SEO criteria.

**SERP:** Use SerpAPI, DataForSEO, ValueSERP, or mock data. Minimum per result: rank, URL, title, snippet. Agent must extract themes and topics to inform the outline.

**Quality bar:** Primary keyword in title and intro, proper header structure, coverage of related subtopics, human-sounding copy.

**Linking:** 3–5 internal links (anchor text + target page/topic); 2–4 external refs (authoritative sources + placement).

### Bonus

Job status tracking (pending, running, completed, failed); durability and resume after crash; content quality scorer with revisions; FAQ from SERP; tests that validate SEO constraints.

### Deliverables

Working code, README with run instructions, at least one input-to-output example, short design notes, tests.
