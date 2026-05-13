// lib/api.ts — typed API client for the FastAPI backend

import type { AnalysisResults, Job, TokenUsage } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { ...init?.headers },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }

  return res.json() as Promise<T>;
}

// ── Analyze ───────────────────────────────────────────────────────────────────

export async function uploadAudio(
  file: File,
  options: {
    meetingTitle: string;
    provider: string;
    skipPreprocess: boolean;
    skipCorrection: boolean;
    skipSentiment: boolean;
    skipExtraction: boolean;
  }
): Promise<{ job_id: string; status: string }> {
  const form = new FormData();
  form.append("audio", file);
  form.append("meeting_title", options.meetingTitle);
  form.append("provider", options.provider);
  form.append("skip_preprocess", String(options.skipPreprocess));
  form.append("skip_correction", String(options.skipCorrection));
  form.append("skip_sentiment", String(options.skipSentiment));
  form.append("skip_extraction", String(options.skipExtraction));

  return apiFetch("/api/analyze", { method: "POST", body: form });
}

// ── Status / Results ──────────────────────────────────────────────────────────

export async function getJobStatus(jobId: string): Promise<Job> {
  return apiFetch(`/api/status/${jobId}`);
}

export async function getResults(jobId: string): Promise<AnalysisResults> {
  return apiFetch(`/api/results/${jobId}`);
}

export function getRecapUrl(jobId: string): string {
  return `${BASE_URL}/api/results/${jobId}/recap`;
}

// ── Jobs list ─────────────────────────────────────────────────────────────────

export async function listJobs(): Promise<Job[]> {
  return apiFetch("/api/jobs");
}

// ── Tokens ────────────────────────────────────────────────────────────────────

export async function getTokenUsage(): Promise<{
  today: TokenUsage;
  history: TokenUsage[];
}> {
  return apiFetch("/api/tokens");
}

// ── Cache ─────────────────────────────────────────────────────────────────────

export async function getCacheStats(): Promise<{
  total: number;
  size_kb: number;
  namespaces: Record<string, number>;
}> {
  return apiFetch("/api/cache/stats");
}

export async function clearCache(): Promise<{ cleared: number }> {
  return apiFetch("/api/cache", { method: "DELETE" });
}
