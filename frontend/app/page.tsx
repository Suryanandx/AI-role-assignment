"use client";

import { useState } from "react";
import { getJob } from "@/lib/graphql";

export default function Home() {
  const [jobId, setJobId] = useState("");
  const [result, setResult] = useState<
    { id: string; status: string; topic: string } | null | "loading" | "error"
  >(null);

  async function handleFetch() {
    if (!jobId.trim()) return;
    setResult("loading");
    try {
      const job = await getJob(jobId.trim());
      setResult(job ?? "error");
    } catch {
      setResult("error");
    }
  }

  return (
    <main style={{ padding: "2rem", maxWidth: 640, margin: "0 auto" }}>
      <h1 style={{ marginBottom: "1rem" }}>Job lookup</h1>
      <p style={{ marginBottom: "1rem", color: "#666" }}>
        Enter a job ID to query the backend GraphQL API.
      </p>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}>
        <input
          type="text"
          value={jobId}
          onChange={(e) => setJobId(e.target.value)}
          placeholder="Job ID (UUID)"
          style={{
            flex: 1,
            padding: "0.5rem",
            fontSize: "1rem",
          }}
          onKeyDown={(e) => e.key === "Enter" && handleFetch()}
        />
        <button
          type="button"
          onClick={handleFetch}
          disabled={result === "loading"}
          style={{
            padding: "0.5rem 1rem",
            fontSize: "1rem",
            cursor: result === "loading" ? "not-allowed" : "pointer",
          }}
        >
          {result === "loading" ? "Loading…" : "Fetch"}
        </button>
      </div>
      {result === "loading" && <p>Loading…</p>}
      {result === "error" && (
        <p style={{ color: "#c00" }}>Not found or request failed.</p>
      )}
      {result && result !== "loading" && result !== "error" && (
        <pre
          style={{
            padding: "1rem",
            background: "#f5f5f5",
            borderRadius: 4,
            overflow: "auto",
          }}
        >
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </main>
  );
}
