"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { createJob, getJobFull } from "@/lib/graphql";

const WORD_COUNT_OPTIONS = [500, 1000, 1500, 2000, 2500, 3000];
const LANGUAGE_OPTIONS = [
  { value: "en", label: "English" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
];

type View = "form" | "created";

export default function Home() {
  const router = useRouter();
  const [view, setView] = useState<View>("form");
  const [topic, setTopic] = useState("");
  const [wordCount, setWordCount] = useState(1500);
  const [language, setLanguage] = useState("en");
  const [jobId, setJobId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [lookupId, setLookupId] = useState("");
  const [lookupLoading, setLookupLoading] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState(false);

  async function handleCreateJob() {
    if (!topic.trim()) return;
    setError(null);
    try {
      const id = await createJob({
        topic: topic.trim(),
        word_count: wordCount,
        language,
      });
      setJobId(id);
      setView("created");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    }
  }

  async function handleLookup() {
    if (!lookupId.trim()) return;
    setError(null);
    setLookupLoading(true);
    try {
      const result = await getJobFull(lookupId.trim());
      if (result) {
        router.push(`/job/${lookupId.trim()}`);
      } else {
        setError("Job not found.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLookupLoading(false);
    }
  }

  async function handleCopyId() {
    try {
      await navigator.clipboard.writeText(jobId);
      setCopyFeedback(true);
      setTimeout(() => setCopyFeedback(false), 2000);
    } catch {
      setCopyFeedback(false);
    }
  }

  return (
    <div className="container">
      <header className="header">
        <h1>SEO Article Generator</h1>
        <p style={{ color: "var(--muted)", fontSize: "0.9rem", marginTop: "0.25rem" }}>
          Create a job, then run the pipeline and view the generated article.
        </p>
      </header>

      {view === "form" && (
        <>
          {error && (
            <section className="card" style={{ borderColor: "var(--danger)" }}>
              <p style={{ color: "var(--danger)", margin: 0 }}>{error}</p>
            </section>
          )}
          <section className="card">
            <h2>Create job</h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <label className="label" htmlFor="topic">
                  Topic or primary keyword
                </label>
                <input
                  id="topic"
                  className="input"
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g. best productivity tools for remote teams"
                />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div>
                  <label className="label" htmlFor="wordCount">
                    Word count
                  </label>
                  <select
                    id="wordCount"
                    className="select"
                    value={wordCount}
                    onChange={(e) => setWordCount(Number(e.target.value))}
                  >
                    {WORD_COUNT_OPTIONS.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label" htmlFor="language">
                    Language
                  </label>
                  <select
                    id="language"
                    className="select"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                  >
                    {LANGUAGE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <button
                type="button"
                className="btn btnPrimary"
                onClick={handleCreateJob}
                disabled={!topic.trim()}
              >
                Create job
              </button>
            </div>
          </section>

          <section className="card">
            <h2>Look up existing job</h2>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "flex-end" }}>
              <div style={{ flex: 1 }}>
                <label className="label" htmlFor="lookupId">
                  Job ID (UUID)
                </label>
                <input
                  id="lookupId"
                  className="input"
                  type="text"
                  value={lookupId}
                  onChange={(e) => setLookupId(e.target.value)}
                  placeholder="Paste job ID from a previous run"
                />
              </div>
              <button
                type="button"
                className="btn btnSecondary"
                onClick={handleLookup}
                disabled={!lookupId.trim() || lookupLoading}
              >
                {lookupLoading ? "Loading…" : "Fetch"}
              </button>
            </div>
          </section>
        </>
      )}

      {view === "created" && (
        <section className="card">
          <h2>Job created</h2>
          <p style={{ marginBottom: "0.75rem" }}>
            Use the job ID below to view progress or run the pipeline.
          </p>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              flexWrap: "wrap",
              marginBottom: "1rem",
            }}
          >
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
              onClick={handleCopyId}
              style={{ padding: "0.35rem 0.75rem", fontSize: "0.875rem" }}
            >
              {copyFeedback ? "Copied" : "Copy"}
            </button>
          </div>
          <Link href={`/job/${jobId}`} className="btn btnPrimary">
            View job
          </Link>
        </section>
      )}
    </div>
  );
}
