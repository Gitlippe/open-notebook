/**
 * Artifact generation types — mirrors the OpenAPI contract at
 * tests/artifacts/reference/artifact_openapi.json
 */

// ---------------------------------------------------------------------------
// Artifact type identifiers (union of all 14 registered types)
// ---------------------------------------------------------------------------

export type ArtifactTypeId =
  | 'briefing'
  | 'data_tables'
  | 'faq'
  | 'flashcards'
  | 'infographic'
  | 'mindmap'
  | 'paper_figure'
  | 'pitch_deck'
  | 'quiz'
  | 'research_review'
  | 'slide_deck'
  | 'study_guide'
  | 'timeline'
  | 'video_overview'

/** All registered artifact type IDs as a tuple for runtime iteration. */
export const ARTIFACT_TYPE_IDS: readonly ArtifactTypeId[] = [
  'briefing',
  'data_tables',
  'faq',
  'flashcards',
  'infographic',
  'mindmap',
  'paper_figure',
  'pitch_deck',
  'quiz',
  'research_review',
  'slide_deck',
  'study_guide',
  'timeline',
  'video_overview',
] as const

// ---------------------------------------------------------------------------
// API shapes
// ---------------------------------------------------------------------------

/** Single entry returned by GET /api/artifacts/types */
export interface ArtifactType {
  type: ArtifactTypeId
  description: string
}

/** ArtifactSourceIn — a piece of content to be processed into an artifact */
export interface ArtifactSource {
  /** Source title or identifier */
  title: string
  /** Raw text content */
  content: string
  url?: string | null
  author?: string | null
  published_at?: string | null
  metadata?: Record<string, unknown>
}

/** ArtifactFileOut — a generated file reference */
export interface ArtifactFile {
  path: string
  mime_type: string
  description?: string | null
}

/** Provenance call record (single LLM invocation) */
export interface ArtifactProvenanceCall {
  prompt_hash?: string | null
  tokens_in?: number | null
  tokens_out?: number | null
  latency_ms?: number | null
  attempt?: number | null
}

/** GenerationProvenance — attached to every completed ArtifactJobResult */
export interface ArtifactProvenance {
  model_id?: string | null
  provider?: string | null
  run_id?: string | null
  calls?: ArtifactProvenanceCall[]
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// Request / response bodies
// ---------------------------------------------------------------------------

/** POST /api/artifacts/generate — request body */
export interface ArtifactGenerateRequest {
  /** e.g. 'briefing', 'slide_deck' */
  artifact_type: ArtifactTypeId | string
  sources?: ArtifactSource[]
  notebook_id?: string | null
  title?: string | null
  /** Arbitrary renderer / generator configuration */
  config?: Record<string, unknown>
  model_id?: string | null
  output_dir?: string | null
}

/** POST /api/artifacts/generate — success response */
export interface ArtifactJobSubmitted {
  job_id: string
  status: string
}

/** GET /api/artifacts/jobs/{job_id} — response */
export interface ArtifactJobResult {
  status: ArtifactJobStatus
  artifact_type?: string | null
  title?: string | null
  summary?: string | null
  structured?: Record<string, unknown>
  files?: ArtifactFile[]
  metadata?: Record<string, unknown>
  provenance?: ArtifactProvenance | null
  error?: string | null
  generated_at?: string | null
}

// ---------------------------------------------------------------------------
// Job status
// ---------------------------------------------------------------------------

export type ArtifactJobStatus =
  | 'submitted'
  | 'running'
  | 'completed'
  | 'failed'
  | string

export const TERMINAL_ARTIFACT_STATUSES: ArtifactJobStatus[] = ['completed', 'failed']
