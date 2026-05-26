export type User = {
  id: number;
  email: string;
  role: "user" | "admin";
  created_at: string;
};

export type Source = {
  source: string;
  score: number;
  chunk_index: number;
  excerpt: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
};

export type HealthInfo = {
  status: string;
  llm_provider_active?: string;
  llm_provider_configured?: string;
  knowledge_points?: number;
};

export type KnowledgeFile = {
  name: string;
  size: number;
  mod_time: string;
};

export type IngestResult = {
  files: number;
  chunks: number;
  collection: string;
  total_points: number;
};

export type PhaseInfo = {
  key: string;
  title: string;
  description: string;
  status: "locked" | "active" | "completed" | "blocked";
  progress_pct: number;
  order: number;
  notes?: string | null;
};

export type EscalationInfo = {
  id: number;
  phase_key: string;
  level: number;
  title: string;
  description: string;
  status: string;
  created_at: string;
};

export type AuditEntry = {
  id: number;
  actor_email: string;
  action: string;
  details?: string | null;
  created_at: string;
};

export type MatrixItem = {
  name: string;
  program_level: number;
  industry_demand_pct: number;
  industry_level_est: number;
  gap_type: string;
};

export type CompetencyMatrix = {
  workspace_id: number;
  industry?: string | null;
  vacancy_count: number;
  summary: { total: number; gaps: number; aligned: number; excess: number };
  items: MatrixItem[];
};

export type CompanyInfo = {
  id: number;
  name: string;
  industry?: string | null;
  region?: string | null;
  website?: string | null;
  score?: number | null;
  score_breakdown?: Record<string, number>;
  status: string;
  in_shortlist: boolean;
  verified: boolean;
  has_education_program: boolean;
  contact_name?: string | null;
  contact_email?: string | null;
  contact_role?: string | null;
  size_category?: string | null;
  source: string;
};

export type CommunicationInfo = {
  id: number;
  company_id: number | null;
  company_name?: string | null;
  comm_type: string;
  tone: string;
  subject: string;
  body: string;
  value_proposition?: string | null;
  status: string;
  approved_by?: string | null;
  version: number;
};

export type TouchPointInfo = {
  id: number;
  step_order: number;
  title: string;
  days_after_start: number;
  channel: string;
  status: string;
};

export type ShortlistCommItem = {
  company: { id: number; name: string; score?: number | null };
  communications: CommunicationInfo[];
  touch_plan: TouchPointInfo[];
};

export type DashboardData = {
  workspace: {
    id: number;
    name: string;
    industry?: string | null;
    phases: PhaseInfo[];
    open_escalations: number;
  };
  escalations: EscalationInfo[];
  recent_audit: AuditEntry[];
};
