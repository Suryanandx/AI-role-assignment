"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  getJobFull,
  runPipeline,
  retryJob,
  type JobFull,
} from "@/lib/graphql";

const POLL_INTERVAL_MS = 2000;

const STEP_LABELS: Record<string, string> = {
  serp_analysis: "SERP Analysis",
  outline: "Outline Generation",
  article: "Article Writing",
  metadata: "Metadata & Links",
  faq: "FAQ Generation",
  validation: "Validation",
  revision: "Revision",
};

const STEP_ORDER = ["serp_analysis", "outline", "article", "metadata", "faq", "validation"];

function PipelineProgress({ currentStep }: { currentStep: string | null }) {
  if (!currentStep) return null;
  const currentIndex = STEP_ORDER.indexOf(currentStep);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", marginTop: "0.5rem" }}>
      <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>Pipeline progress</span>
      <div style={{ display: "flex", gap: "0.25rem", flexWrap: "wrap" }}>
        {STEP_ORDER.map((step, i) => {
          const isDone = i < currentIndex;
          const isActive = step === currentStep;
          return (
            <span
              key={step}
              style={{
                fontSize: "0.75rem",
                padding: "0.2rem 0.5rem",
                borderRadius: "var(--radius)",
                background: isDone
                  ? "var(--success, #22c55e)"
                  : isActive
                    ? "var(--accent)"
                    : "var(--card-border)",
                color: isDone || isActive ? "#fff" : "var(--muted)",
                fontWeight: isActive ? 600 : 400,
              }}
            >
              {STEP_LABELS[step] ?? step}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function JobIdCopy({ jobId }: { jobId: string }) {
  const [copied, setCopied] = useState(false);
  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(jobId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
      <code
        style={{
          fontSize: "0.85rem",
          padding: "0.35rem 0.5rem",
          background: "var(--card-border)",
          borderRadius: "var(--radius)",
          wordBreak: "break-all",
        }}
      >
        {jobId}
      </code>
      <button
        type="button"
        className="btn btnSecondary"
        onClick={handleCopy}
        style={{ padding: "0.35rem 0.75rem", fontSize: "0.875rem" }}
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const className =
    status === "completed"
      ? "badgeCompleted"
      : status === "failed"
        ? "badgeFailed"
        : status === "running"
          ? "badgeRunning"
          : "badgePending";
  return <span className={`badge ${className}`}>{status}</span>;
}

export default function JobPage() {
  const params = useParams();
  const id = typeof params.id === "string" ? params.id : "";
  const [job, setJob] = useState<JobFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [runLoading, setRunLoading] = useState(false);
  const [retryLoading, setRetryLoading] = useState(false);
  const [refreshLoading, setRefreshLoading] = useState(false);

  useEffect(() => {
    if (!id) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setJob(null);
    getJobFull(id)
      .then((data) => {
        if (!cancelled) setJob(data);
      })
      .catch(() => {
        if (!cancelled) setJob(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    if (!id || !job || (job.status !== "pending" && job.status !== "running")) {
      return;
    }
    const fetchJob = () => {
      getJobFull(id).then((data) => {
        if (data) setJob(data);
      });
    };
    fetchJob();
    const timer = setInterval(fetchJob, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [id, job?.status]);

  async function handleRunPipeline() {
    if (!id) return;
    setRunLoading(true);
    try {
      const result = await runPipeline(id);
      setJob(result);
    } catch {
      setRunLoading(false);
      try {
        const latest = await getJobFull(id);
        if (latest) setJob(latest);
      } catch {
        // ignore refetch error
      }
    } finally {
      setRunLoading(false);
    }
  }

  async function handleRetry() {
    if (!id) return;
    setRetryLoading(true);
    try {
      const result = await retryJob(id);
      setJob(result);
    } catch {
      setRetryLoading(false);
      try {
        const latest = await getJobFull(id);
        if (latest) setJob(latest);
      } catch {
        // ignore refetch error
      }
    } finally {
      setRetryLoading(false);
    }
  }

  async function handleRefresh() {
    if (!id) return;
    setRefreshLoading(true);
    try {
      const data = await getJobFull(id);
      if (data) setJob(data);
    } finally {
      setRefreshLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="container">
        <p style={{ color: "var(--muted)" }}>Loading job…</p>
      </div>
    );
  }

  if (!id || job === null) {
    return (
      <div className="container">
        <section className="card">
          <h2>Job not found</h2>
          <p style={{ color: "var(--muted)", marginBottom: "1rem" }}>
            The job ID may be invalid or the job was not created.
          </p>
          <Link href="/" className="btn btnPrimary">
            Create another
          </Link>
        </section>
      </div>
    );
  }

  const sections = job.article_with_faq?.sections ?? job.article?.sections ?? [];
  const faqList = job.article_with_faq?.faq ?? job.faq ?? [];

  return (
    <div className="container">
      <header className="header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "0.5rem" }}>
        <div>
          <h1>SEO Article Generator</h1>
          <p style={{ color: "var(--muted)", fontSize: "0.9rem", marginTop: "0.25rem" }}>
            Job details and generated article
          </p>
        </div>
        <Link href="/" className="btn btnSecondary">
          Create another
        </Link>
      </header>

      <section className="card">
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
            <StatusBadge status={job.status} />
            <span style={{ color: "var(--muted)", fontSize: "0.9rem" }}>{job.topic}</span>
            {job.quality_score != null && (
              <span style={{ fontSize: "0.9rem" }}>
                Quality: {(job.quality_score * 100).toFixed(0)}%
              </span>
            )}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "0.5rem" }}>
            <div>
              <span className="label">Job ID</span>
              <JobIdCopy jobId={id} />
            </div>
            <button
              type="button"
              className="btn btnSecondary"
              onClick={handleRefresh}
              disabled={refreshLoading}
              style={{ padding: "0.35rem 0.75rem", fontSize: "0.875rem" }}
            >
              {refreshLoading ? "Refreshing…" : "Refresh"}
            </button>
          </div>
          {(job.status === "pending" || (job.status === "running" && runLoading)) && (
            <div style={{ marginTop: "0.5rem" }}>
              <button
                type="button"
                className="btn btnPrimary"
                onClick={handleRunPipeline}
                disabled={runLoading}
              >
                {runLoading ? "Running…" : "Run pipeline"}
              </button>
              {job.status === "pending" && !runLoading && (
                <p style={{ color: "var(--muted)", fontSize: "0.875rem", marginTop: "0.5rem" }}>
                  This may take a minute.
                </p>
              )}
            </div>
          )}
          {job.error && (
            <p style={{ color: "var(--danger)", marginTop: "0.5rem", marginBottom: 0 }}>
              {job.error}
            </p>
          )}
        </div>
      </section>

      {job.status === "failed" && (
        <section className="card" style={{ borderColor: "var(--danger)" }}>
          <h2>Error</h2>
          <p style={{ color: "var(--danger)", marginBottom: "0.75rem" }}>{job.error}</p>
          <button
            type="button"
            className="btn btnPrimary"
            onClick={handleRetry}
            disabled={retryLoading}
          >
            {retryLoading ? "Retrying…" : "Retry from last checkpoint"}
          </button>
        </section>
      )}

      {job.status === "completed" && (
        <>
          {job.metadata && (
            <section className="card">
              <h2>SEO metadata</h2>
              <dl style={{ margin: 0, display: "grid", gap: "0.5rem" }}>
                <div>
                  <dt style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: "0.2rem" }}>Title tag</dt>
                  <dd style={{ margin: 0 }}>{job.metadata.title_tag}</dd>
                </div>
                <div>
                  <dt style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: "0.2rem" }}>Meta description</dt>
                  <dd style={{ margin: 0 }}>{job.metadata.meta_description}</dd>
                </div>
                <div>
                  <dt style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: "0.2rem" }}>Primary keyword</dt>
                  <dd style={{ margin: 0 }}>{job.metadata.primary_keyword}</dd>
                </div>
                {job.metadata.secondary_keywords?.length > 0 && (
                  <div>
                    <dt style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: "0.2rem" }}>Secondary keywords</dt>
                    <dd style={{ margin: 0 }}>{job.metadata.secondary_keywords.join(", ")}</dd>
                  </div>
                )}
              </dl>
            </section>
          )}

          {sections.length > 0 && (
            <section className="card">
              <h2>Article</h2>
              <div className={`articleContent articleReading`}>
                {sections.map((s, i) => (
                  <div key={i}>
                    {s.level === 1 && <h1>{s.heading}</h1>}
                    {s.level === 2 && <h2>{s.heading}</h2>}
                    {(s.level === 3 || s.level > 3) && <h3>{s.heading}</h3>}
                    <p style={{ whiteSpace: "pre-wrap" }}>{s.content}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {faqList.length > 0 && (
            <section className="card">
              <h2>FAQ</h2>
              {faqList.map((item, i) => (
                <div key={i} className="faqItem">
                  <strong>{item.question}</strong>
                  <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{item.answer}</p>
                </div>
              ))}
            </section>
          )}

          {job.internal_links?.length > 0 && (
            <section className="card">
              <h2>Internal links</h2>
              <ul style={{ marginLeft: "1.25rem" }}>
                {job.internal_links.map((l, i) => (
                  <li key={i}>
                    &quot;{l.anchor_text}&quot; → {l.target_topic}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {job.external_refs?.length > 0 && (
            <section className="card">
              <h2>External references</h2>
              <ul style={{ marginLeft: "1.25rem" }}>
                {job.external_refs.map((r, i) => (
                  <li key={i}>
                    <a href={r.url} target="_blank" rel="noopener noreferrer">
                      {r.title}
                    </a>
                    {r.placement_context && ` (${r.placement_context})`}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}

      {job.status === "pending" && !runLoading && (
        <section className="card">
          <p style={{ color: "var(--muted)" }}>
            Job is pending. Click &quot;Run pipeline&quot; above to generate the article.
          </p>
        </section>
      )}

      {job.status === "running" && !runLoading && (
        <section className="card">
          <p style={{ color: "var(--muted)", marginBottom: "0.5rem" }}>
            Pipeline running… Status updates automatically.
          </p>
          <PipelineProgress currentStep={job.current_step} />
        </section>
      )}
    </div>
  );
}
