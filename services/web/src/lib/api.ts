"use client";

import { authHeaders, clearSession } from "./auth";
import type { HealthInfo, IngestResult, KnowledgeFile, Source, User } from "./types";

async function handleResponse<T>(res: Response, options?: { redirectOn401?: boolean }): Promise<T> {
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && options?.redirectOn401 !== false) {
    clearSession();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("unauthorized");
  }
  if (!res.ok) {
    throw new Error((data as { error?: string }).error || `HTTP ${res.status}`);
  }
  return data as T;
}

export async function login(email: string, password: string) {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse<{ token: string; user: User }>(res, { redirectOn401: false });
}

export async function register(email: string, password: string) {
  const res = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse<{ token: string; user: User }>(res, { redirectOn401: false });
}

export async function fetchHealth(): Promise<HealthInfo> {
  const res = await fetch("/api/health");
  return handleResponse<HealthInfo>(res, { redirectOn401: false });
}

export async function sendChat(message: string, sessionId: string) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  return handleResponse<{
    session_id: string;
    answer: string;
    sources: Source[];
  }>(res);
}

export async function sendFeedback(payload: {
  session_id: string;
  rating: number;
  question: string;
  answer: string;
}) {
  const res = await fetch("/api/feedback", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  return handleResponse<{ status: string }>(res);
}

export async function listKnowledgeFiles(): Promise<{ files: KnowledgeFile[] }> {
  const res = await fetch("/api/admin/files", { headers: authHeaders() });
  return handleResponse(res);
}

export async function uploadKnowledgeFile(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/api/admin/files", {
    method: "POST",
    headers: authHeaders(),
    body: fd,
  });
  return handleResponse<{ name: string; status: string }>(res);
}

export async function deleteKnowledgeFile(name: string) {
  const res = await fetch(`/api/admin/files/${encodeURIComponent(name)}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return handleResponse<{ status: string; name: string }>(res);
}

export async function ingestKnowledge(): Promise<IngestResult> {
  const res = await fetch("/api/admin/ingest", {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse<IngestResult>(res);
}
