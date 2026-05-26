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
