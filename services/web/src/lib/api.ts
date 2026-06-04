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
      return "Нужна роль модератора";
    }
    if (obj.detail === "curator required") {
      return "Нужна роль куратора или модератора";
    }
    if (obj.detail === "access denied") {
      return "Недостаточно прав для этого раздела";
    }
    if (obj.detail === "student required") {
      return "Доступно только ученикам";
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

export async function createStaffUser(payload: {
  email: string;
  password: string;
  role: "curator" | "admin";
}) {
  const res = await fetch("/api/admin/users", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  return handleResponse<{ user: User }>(res);
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

export async function collectVacancies(
  query: string,
  maxPages = 2,
  provider: "hh" | "superjob" = "hh",
) {
  const res = await fetch("/api/ed/competencies/collect", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ query, max_pages: maxPages, provider }),
  });
  return handleResponse<{
    vacancies_collected: number;
    vacancies_new: number;
    skills_found: number;
    query: string;
    provider?: string;
    demo_mode?: boolean;
    message?: string | null;
  }>(res);
}

export async function exportCompetencyMatrixCsv(): Promise<Blob> {
  const res = await fetch("/api/ed/competencies/matrix/export?format=csv", {
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || res.statusText);
  }
  return res.blob();
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

export async function enrichCompaniesBatch(limit = 10) {
  const res = await fetch("/api/ed/companies/enrich-batch", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ limit }),
  });
  return handleResponse<{ attempted: number; enriched: number; errors: string[] }>(res);
}

export async function downloadPresentationPdf(): Promise<Blob> {
  const res = await fetch("/api/ed/comms/presentation.pdf", { headers: authHeaders() });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || res.statusText);
  }
  return res.blob();
}

export async function fetchMemoryStats() {
  const res = await fetch("/api/ed/memory/stats", { headers: authHeaders() });
  return handleResponse<{
    patterns_total: number;
    patterns_success: number;
    outcomes_total: number;
    strategy_memory_enabled: boolean;
  }>(res);
}

export async function syncStrategyMemory() {
  const res = await fetch("/api/ed/memory/sync", {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse<{ outcomes_scanned: number; patterns_upserted: number }>(res);
}

export async function exportQloraDataset() {
  const res = await fetch("/api/ed/memory/qlora/export", {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse<{
    records: number;
    source_outcomes: number;
    path: string;
    base_model_hint: string;
  }>(res);
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

export async function discoverCompaniesAsync(query?: string, maxPages = 5) {
  const res = await fetch("/api/ed/companies/discover/async", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ query, max_pages: maxPages }),
  });
  return handleResponse<{ task_id: string; status: string }>(res);
}

export async function fetchDiscoverJobStatus(taskId: string) {
  const res = await fetch(`/api/ed/companies/discover/jobs/${taskId}`, {
    headers: authHeaders(),
  });
  return handleResponse<{
    task_id: string;
    status: string;
    result?: {
      added: number;
      total: number;
      query: string;
      demo_mode?: boolean;
      message?: string | null;
    };
    error?: string;
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
    letters_delivered: number;
    letters_opened: number;
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
      classification_confidence?: number;
      classification_method?: string;
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
    classification_confidence?: number;
    classification_method?: string;
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

export async function fetchProjectCatalog(competencies?: string) {
  const qs = competencies?.trim()
    ? `?competencies=${encodeURIComponent(competencies.trim())}`
    : "";
  const res = await fetch(`/api/ed/projects/catalog${qs}`, { headers: authHeaders() });
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
      enrollment_count?: number;
      seats_left?: number;
    }>;
  }>(res);
}

export type CatalogProjectRole = {
  id: number;
  title: string;
  skills?: string | null;
  hours_per_week?: number | null;
  slots: number;
  enrolled_count: number;
  seats_left: number;
};

export type CatalogProjectDetail = {
  id: number;
  title: string;
  company_name?: string | null;
  description?: string | null;
  spec_markdown?: string | null;
  team_size?: number | null;
  duration_weeks?: number | null;
  competencies?: string | null;
  published_at?: string | null;
  enrollment_count?: number;
  seats_left?: number;
  roles?: CatalogProjectRole[];
  my_enrollment?: {
    id: number;
    role_id?: number | null;
    role_title?: string | null;
    status: string;
  } | null;
};

export async function fetchCatalogProject(projectId: number) {
  const res = await fetch(`/api/ed/projects/catalog/${projectId}`, {
    headers: authHeaders(),
  });
  return handleResponse<CatalogProjectDetail>(res);
}

export async function enrollInProject(projectId: number, roleId?: number) {
  const res = await fetch(`/api/ed/projects/catalog/${projectId}/enroll`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ role_id: roleId ?? null }),
  });
  return handleResponse<{ id: number; project_id: number; role_title?: string | null; status: string }>(
    res,
  );
}

export async function withdrawFromProject(projectId: number) {
  const res = await fetch(`/api/ed/projects/catalog/${projectId}/enroll`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return handleResponse<{ status: string; project_id: number }>(res);
}

export async function fetchMyEnrollments() {
  const res = await fetch("/api/ed/projects/my-enrollments", { headers: authHeaders() });
  return handleResponse<{
    items: Array<{
      id: number;
      project_id: number;
      project_title: string;
      role_title?: string | null;
      status: string;
    }>;
  }>(res);
}

export async function syncProjectRoles(projectId: number) {
  const res = await fetch(`/api/ed/projects/${projectId}/roles/sync`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse<{ roles: CatalogProjectRole[] }>(res);
}

export async function fetchCompetencyChart() {
  const res = await fetch("/api/ed/competencies/matrix/chart", { headers: authHeaders() });
  return handleResponse<{
    summary: { total: number; gaps: number; aligned: number; excess: number };
    by_gap_type: Array<{ gap_type: string; count: number }>;
    top_gaps: Array<{
      name: string;
      program_level: number;
      industry_demand_pct: number;
      industry_level_est: number;
      gap_type: string;
    }>;
    comparison: Array<{
      name: string;
      program_level: number;
      industry_level_est: number;
      industry_demand_pct: number;
      gap_type: string;
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

export async function deleteAccount(password: string) {
  const res = await fetch("/api/auth/account", {
    method: "DELETE",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ password }),
  });
  return handleResponse<{ status: string }>(res, { redirectOn401: false });
}

export async function fetchScoringWeights() {
  const res = await fetch("/api/ed/companies/scoring/weights", { headers: authHeaders() });
  return handleResponse<{ weights: Record<string, number> }>(res);
}

export async function updateScoringWeights(weights: Record<string, number>) {
  const res = await fetch("/api/ed/companies/scoring/weights", {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(weights),
  });
  return handleResponse<{ weights: Record<string, number>; rescored: number }>(res);
}

export async function fetchStudentProfile() {
  const res = await fetch("/api/ed/projects/profile", { headers: authHeaders() });
  return handleResponse<{ profile: { student_email: string; skills: string; notes?: string | null } | null }>(
    res,
  );
}

export async function saveStudentProfile(skills: string, notes?: string) {
  const res = await fetch("/api/ed/projects/profile", {
    method: "PUT",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ skills, notes: notes ?? null }),
  });
  return handleResponse<{ profile: { student_email: string; skills: string; notes?: string | null } }>(res);
}

export async function fetchProjectRecommendations(limit = 10) {
  const res = await fetch(`/api/ed/projects/recommendations?limit=${limit}`, {
    headers: authHeaders(),
  });
  return handleResponse<{
    items: Array<{
      id: number;
      title: string;
      company_name?: string | null;
      match_score?: number;
      skill_overlap?: number;
      matched_skills?: string[];
      seats_left?: number;
      competencies?: string | null;
    }>;
  }>(res);
}

export type CommVersion = {
  id: number;
  version: number;
  subject?: string | null;
  body?: string | null;
  value_proposition?: string | null;
  edited_by?: string | null;
  created_at?: string | null;
};

export async function fetchCommunicationVersions(commId: number) {
  const res = await fetch(`/api/ed/comms/${commId}/versions`, { headers: authHeaders() });
  return handleResponse<{ versions: CommVersion[] }>(res);
}
