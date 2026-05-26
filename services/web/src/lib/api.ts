"use client";

import { authHeaders, clearSession } from "./auth";
import type {
  CommunicationInfo,
  CompanyInfo,
  CompetencyMatrix,
  DashboardData,
  HealthInfo,
  IngestResult,
  KnowledgeFile,
  ShortlistCommItem,
  Source,
  User,
} from "./types";

function apiErrorMessage(data: unknown, status: number): string {
  if (!data || typeof data !== "object") return `HTTP ${status}`;
  const obj = data as { error?: string; detail?: string | Array<{ msg?: string }> };
  if (obj.error) return obj.error;
  if (typeof obj.detail === "string") {
    if (obj.detail === "admin required") {
      return "Нужна роль admin. Войдите как ADMIN_EMAIL из .env";
    }
    return obj.detail;
  }
  if (Array.isArray(obj.detail)) {
    return obj.detail.map((d) => d.msg || String(d)).join("; ");
  }
  return `HTTP ${status}`;
}

async function handleResponse<T>(res: Response, options?: { redirectOn401?: boolean }): Promise<T> {
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && options?.redirectOn401 !== false) {
    clearSession();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("unauthorized");
  }
  if (!res.ok) {
    throw new Error(apiErrorMessage(data, res.status));
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

export async function fetchDashboard(): Promise<DashboardData> {
  const res = await fetch("/api/ed/dashboard", { headers: authHeaders() });
  return handleResponse<DashboardData>(res);
}

export async function approveIndustry(industry: string, comment?: string) {
  const res = await fetch("/api/ed/industry/approve", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ industry, comment }),
  });
  return handleResponse<DashboardData>(res);
}

export async function fetchCompetencyMatrix(): Promise<CompetencyMatrix> {
  const res = await fetch("/api/ed/competencies/matrix", { headers: authHeaders() });
  return handleResponse<CompetencyMatrix>(res);
}

export async function fetchCompetencyStats() {
  const res = await fetch("/api/ed/competencies/stats", { headers: authHeaders() });
  return handleResponse<{
    program_competencies: number;
    industry_competencies: number;
    vacancies: number;
  }>(res);
}

export async function collectVacancies(query: string, maxPages = 2) {
  const res = await fetch("/api/ed/competencies/collect", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ query, max_pages: maxPages }),
  });
  return handleResponse<{
    vacancies_collected: number;
    vacancies_new: number;
    skills_found: number;
    query: string;
    demo_mode?: boolean;
    message?: string | null;
  }>(res);
}

export async function fetchCompaniesShortlist() {
  const res = await fetch("/api/ed/companies?shortlist_only=true&limit=100", {
    headers: authHeaders(),
  });
  return handleResponse<{ companies: CompanyInfo[] }>(res);
}

export async function fetchCompaniesTop(n: number) {
  const res = await fetch(`/api/ed/companies/top/${n}`, { headers: authHeaders() });
  return handleResponse<{ limit: number; total_in_workspace: number; companies: CompanyInfo[] }>(res);
}

export async function discoverCompanies(query?: string, maxPages = 3) {
  const res = await fetch("/api/ed/companies/discover", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ query, max_pages: maxPages }),
  });
  return handleResponse<{
    added: number;
    total: number;
    query: string;
    demo_mode?: boolean;
    message?: string | null;
  }>(res);
}

export async function seedProgramCompetencies() {
  const res = await fetch("/api/ed/competencies/program/seed", {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse<{ seeded: number }>(res);
}

export async function verifyCompany(id: number) {
  const res = await fetch(`/api/ed/companies/${id}/verify`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse<CompanyInfo>(res);
}

export async function rejectCompany(id: number, reason = "") {
  const res = await fetch(`/api/ed/companies/${id}/reject`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ reason }),
  });
  return handleResponse<CompanyInfo>(res);
}

export async function fetchCommsShortlist() {
  const res = await fetch("/api/ed/comms/shortlist", { headers: authHeaders() });
  return handleResponse<{ items: ShortlistCommItem[] }>(res);
}

export async function fetchFaq() {
  const res = await fetch("/api/ed/comms/faq", { headers: authHeaders() });
  return handleResponse<{ faq: CommunicationInfo | null }>(res);
}

export async function generateLetter(companyId: number, tone: "formal" | "informal") {
  const res = await fetch(`/api/ed/comms/companies/${companyId}/generate`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ tone }),
  });
  return handleResponse<CommunicationInfo>(res);
}

export async function generateLettersBatch(tone: "formal" | "informal") {
  const res = await fetch("/api/ed/comms/generate-batch", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ tone }),
  });
  return handleResponse<{ generated: number; tone: string }>(res);
}

export async function generateFaq() {
  const res = await fetch("/api/ed/comms/faq/generate", {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse<CommunicationInfo>(res);
}

export async function updateCommunication(
  commId: number,
  data: { subject?: string; body?: string; value_proposition?: string },
) {
  const res = await fetch(`/api/ed/comms/${commId}`, {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  return handleResponse<CommunicationInfo>(res);
}

export async function approveCommunication(commId: number) {
  const res = await fetch(`/api/ed/comms/${commId}/approve`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse<CommunicationInfo>(res);
}

export async function fetchOutreachDashboard() {
  const res = await fetch("/api/ed/outreach/dashboard", { headers: authHeaders() });
  return handleResponse<{
    smtp_enabled: boolean;
    letters_approved: number;
    letters_sent: number;
    letters_pending: number;
    inbound_count: number;
    followups_due: number;
    queue: Array<{
      id: number;
      company_id: number;
      company_name: string;
      contact_email?: string | null;
      subject: string;
      delivery_status: string;
    }>;
    recent_responses: Array<{
      id: number;
      company_id: number;
      company_name: string;
      subject?: string | null;
      body?: string | null;
      classification?: string | null;
      auto_handled: boolean;
    }>;
    followups: Array<{
      touch_id: number;
      company_id: number;
      company_name: string;
      title: string;
    }>;
    companies: Array<{
      id: number;
      name: string;
      in_shortlist: boolean;
      status: string;
    }>;
  }>(res);
}

export async function sendOutreachLetter(commId: number, useSmtp = false) {
  const res = await fetch(`/api/ed/outreach/communications/${commId}/send`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ use_smtp: useSmtp }),
  });
  return handleResponse(res);
}

export async function recordInboundResponse(
  companyId: number,
  body: string,
  subject = "",
) {
  const res = await fetch(`/api/ed/outreach/companies/${companyId}/inbound`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ subject, body, auto_respond: true }),
  });
  return handleResponse<{
    classification?: string;
    auto_reply?: string | null;
    needs_human?: boolean;
  }>(res);
}

export async function sendFollowup(touchId: number) {
  const res = await fetch(`/api/ed/outreach/followups/${touchId}/send`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse(res);
}

export async function recordAgreement(companyId: number, summary: string) {
  const res = await fetch(`/api/ed/outreach/companies/${companyId}/agreement`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ summary, status: "agreed" }),
  });
  return handleResponse(res);
}

export async function fetchProjectsDashboard() {
  const res = await fetch("/api/ed/projects/dashboard", { headers: authHeaders() });
  return handleResponse<{
    phase_status: string;
    phase_progress: number;
    partners_count: number;
    projects_total: number;
    projects_draft: number;
    projects_approved: number;
    catalog_published: number;
    pending: Array<{
      company_id: number;
      company_name: string;
      agreement_id: number;
      agreement_summary: string;
      project_id: number | null;
      project_status: string | null;
    }>;
    projects: Array<{
      id: number;
      company_id: number | null;
      company_name?: string | null;
      title: string;
      spec_markdown?: string | null;
      status: string;
      catalog_visible: boolean;
      team_size?: number | null;
      duration_weeks?: number | null;
      competencies?: string | null;
    }>;
  }>(res);
}

export async function fetchProjectCatalog() {
  const res = await fetch("/api/ed/projects/catalog", { headers: authHeaders() });
  return handleResponse<{
    items: Array<{
      id: number;
      title: string;
      company_name?: string | null;
      description?: string | null;
      team_size?: number | null;
      duration_weeks?: number | null;
      competencies?: string | null;
      published_at?: string | null;
    }>;
  }>(res);
}

export async function generateProjectTz(companyId: number, agreementId?: number) {
  const res = await fetch(`/api/ed/projects/companies/${companyId}/generate`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ agreement_id: agreementId ?? null }),
  });
  return handleResponse<{
    id: number;
    title: string;
    spec_markdown?: string | null;
    status: string;
  }>(res);
}

export async function updateProject(
  projectId: number,
  body: {
    title?: string;
    spec_markdown?: string;
    team_size?: number;
    duration_weeks?: number;
    competencies?: string;
  },
) {
  const res = await fetch(`/api/ed/projects/${projectId}`, {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  return handleResponse(res);
}

export async function approveProject(projectId: number) {
  const res = await fetch(`/api/ed/projects/${projectId}/approve`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse(res);
}

export async function publishProject(projectId: number) {
  const res = await fetch(`/api/ed/projects/${projectId}/publish`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse(res);
}

export async function completeProjectsPhase() {
  const res = await fetch("/api/ed/projects/phase/complete", {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse<{ status: string; catalog_published: number }>(res);
}

export async function completeCommsPhase() {
  const res = await fetch("/api/ed/comms/phase/complete", {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse<{ approved_letters: number; shortlist: number }>(res);
}

export async function fillShortlist(limit = 3) {
  const res = await fetch("/api/ed/companies/shortlist/fill", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ limit }),
  });
  return handleResponse<{
    added: number;
    company_ids: number[];
    companies: Array<{ id: number; name: string }>;
  }>(res);
}

export async function approveShortlist() {
  const res = await fetch("/api/ed/companies/shortlist/approve", {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse<{ shortlist_count: number; status: string }>(res);
}

export async function resolveEscalation(id: number, comment?: string) {
  const res = await fetch(`/api/ed/escalations/${id}/resolve`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ status: "resolved", comment }),
  });
  return handleResponse(res);
}
