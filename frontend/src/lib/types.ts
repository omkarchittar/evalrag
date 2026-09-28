export interface User {
  id: string;
  name: string;
  email: string;
  role: "admin" | "member";
  active: boolean;
  created_at: string;
}
export interface Session {
  user: User;
  csrf_token: string;
}
export interface Workspace {
  id: string;
  name: string;
  role: "owner" | "editor" | "viewer";
  created_at: string;
}
export interface KnowledgeBase {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  embedding_model: string;
  embedding_dimension: number;
  index_version: number;
  chunk_strategy: string;
  chunk_size: number;
  chunk_overlap: number;
  created_at: string;
}
export interface Document {
  id: string;
  filename: string;
  checksum: string;
  status: string;
  error_code: string | null;
  chunk_count: number;
  size_bytes: number;
  embedding_tokens: number | null;
  ingestion_ms: number | null;
  created_at: string;
}
export interface Page<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}
export interface Source {
  chunk_id: string;
  document_id: string;
  filename: string;
  page: number;
  ordinal: number;
  content: string;
  token_count: number;
  score: number;
}
export interface QueryConfig {
  model: string;
  prompt_version: string;
  top_k: number;
  minimum_score: number;
  agent_mode: boolean;
}
export interface QueryOptions {
  models: string[];
  prompt_versions: string[];
  max_top_k: number;
  max_tool_calls: number;
}
export interface Trace {
  id: string;
  knowledge_base_id: string;
  question: string;
  answer: string | null;
  outcome: string;
  abstained: boolean;
  error_code: string | null;
  created_at: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number | null;
  retrieved: Source[];
  citations: {
    chunk_id: string;
    quote: string;
    valid: boolean;
    claim_index: number;
    reason?: string;
  }[];
  tool_calls: {
    id: string;
    name: string;
    input: unknown;
    output: unknown;
    status: string;
    duration_ms: number;
  }[];
  config: QueryConfig & {
    abstention_reason?: string;
    claims?: { text: string }[];
    answer_validation?: {
      citation_coverage: number;
      citation_correctness: number;
    };
    usage?: unknown[];
    usage_complete?: boolean;
  };
}
export type Scores = Record<string, number | null>;
export interface Overview {
  knowledge_base_count: number;
  documents: Record<string, number>;
  operations: Scores;
  operations_sample_limit: number;
  recent_runs: {
    id: string;
    name: string;
    status: string;
    created_at: string;
  }[];
}
export interface Case {
  id?: string;
  question: string;
  expected_answer: string | null;
  expected_abstention: boolean | null;
  expected_sources: string[];
  expected_tool: string | null;
  tags: string[];
  notes: string;
}
export interface Dataset {
  id: string;
  workspace_id: string;
  name: string;
  version: number;
  case_count: number;
  cases?: Case[];
}
export interface Run {
  id: string;
  name: string;
  workspace_id: string;
  dataset_id: string;
  knowledge_base_id: string;
  status: string;
  total_cases: number;
  completed_cases: number;
  error_code: string | null;
  config: Record<string, unknown>;
  dataset_hash: string;
  corpus_hash: string;
  created_at: string;
  metrics: {
    quality?: Scores;
    coverage?: Scores;
    operations?: Scores;
    failed_cases?: number;
    evaluation_error_rate?: number | null;
    evaluator?: Record<string, unknown>;
  } | null;
}
