export type User = {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
};

export type Workspace = {
  id: string;
  name: string;
  description: string | null;
  created_by_user_id: string;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
  workspace: Workspace;
};

export type WorkspaceMember = {
  id: string;
  workspace_id: string;
  user_id: string;
  role: "owner" | "member";
  created_at: string;
};

export type WorkspaceInvite = {
  id: string;
  workspace_id: string;
  email: string;
  role: "owner" | "member";
  invite_token: string;
  invited_by_user_id: string;
  status: "pending" | "accepted" | "revoked" | "expired";
  expires_at: string;
  accepted_at: string | null;
  created_at: string;
  invite_url: string | null;
};

export type ActivityItem = {
  kind: string;
  entity_id: string;
  title: string;
  created_at: string;
};

export type Project = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  created_by_user_id: string;
  assigned_user_id: string | null;
  created_at: string;
};

export type MessageInput = {
  role: string;
  content: string;
};

export type LearningPreferences = {
  explanation_style?: string | null;
  difficulty?: string | null;
  focus_topics?: string[];
};

export type Source = {
  id: string;
  url: string;
  title: string;
  excerpt: string;
  summary: string;
  published_at: string | null;
  confidence: number;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type ReportSection = {
  id: string;
  heading: string;
  body: string;
  citation_source_ids: string[];
  created_at: string;
};

export type SourceReview = {
  id: string;
  source_id: string;
  reviewer_user_id: string;
  decision: "pending" | "approved" | "rejected";
  note: string | null;
  created_at: string;
};

export type Report = {
  id: string;
  workspace_id: string;
  project_id: string;
  run_id: string | null;
  created_by_user_id: string;
  title: string;
  executive_summary: string;
  body: string;
  status: "draft" | "reviewed" | "final";
  created_at: string;
  sections: ReportSection[];
  sources: Source[];
  source_reviews: SourceReview[];
};

export type Comment = {
  id: string;
  workspace_id: string;
  project_id: string;
  report_id: string | null;
  learning_session_id: string | null;
  user_id: string;
  body: string;
  anchor: string | null;
  created_at: string;
};

export type Checkpoint = {
  id: string;
  learning_session_id: string;
  report_id: string;
  title: string;
  objective: string;
  study_material: string;
  quiz_questions: string[];
  citation_source_ids: string[];
  order_index: number;
  score: number | null;
  passed: boolean | null;
  feedback: string | null;
  last_answers: string[] | null;
  simplified_material: string | null;
  created_at: string;
  updated_at: string;
};

export type LearningSession = {
  id: string;
  workspace_id: string;
  project_id: string;
  report_id: string;
  user_id: string;
  status: "active" | "completed";
  preferred_explanation_style: string | null;
  current_checkpoint_index: number;
  created_at: string;
  updated_at: string;
  checkpoints: Checkpoint[];
  comments: Comment[];
};

export type MasteryRecord = {
  id: string;
  workspace_id: string;
  project_id: string;
  user_id: string;
  topic: string;
  confidence: number;
  last_reviewed_at: string | null;
  next_review_at: string | null;
  review_state: string;
  failed_attempts: number;
  preferred_explanation_style: string | null;
  mastered: boolean;
  confidence_history: number[];
  created_at: string;
  updated_at: string;
};

export type CheckpointSubmissionResponse = {
  checkpoint: Checkpoint;
  mastery_record: MasteryRecord;
  next_recommended_action: string;
};

export type ProjectRun = {
  id: string;
  workspace_id: string;
  project_id: string;
  user_id: string;
  mode: "research" | "learn" | "research_then_learn";
  status: "queued" | "running" | "completed" | "failed";
  input_messages: MessageInput[];
  response_payload: Record<string, unknown>;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  report: Report | null;
  learning_session: LearningSession | null;
};

export type RunReviewFlag = {
  id: string;
  workspace_id: string;
  project_id: string;
  run_id: string;
  report_id: string | null;
  reviewer_user_id: string;
  severity: string;
  note: string;
  created_at: string;
};

export type KnowledgeDocument = {
  id: string;
  workspace_id: string;
  project_id: string;
  created_by_user_id: string;
  kind: "pdf" | "markdown" | "text" | "url" | "note";
  title: string;
  source_uri: string | null;
  metadata_json: Record<string, unknown>;
  status: "queued" | "ready" | "failed";
  created_at: string;
  chunk_count: number;
};

export type KnowledgeSearchHit = {
  document_id: string;
  document_title: string;
  chunk_id: string;
  content: string;
  score: number;
  metadata_json: Record<string, unknown>;
};

export type KnowledgeSearchResponse = {
  query: string;
  hits: KnowledgeSearchHit[];
};

export type BackgroundJob = {
  id: string;
  workspace_id: string | null;
  project_id: string | null;
  user_id: string | null;
  report_id: string | null;
  document_id: string | null;
  job_type:
    | "ingest_document"
    | "ingest_url"
    | "export_report_markdown"
    | "export_report_pdf"
    | "export_learning_session_summary"
    | "export_workspace_summary";
  status: "pending" | "running" | "completed" | "failed";
  payload: Record<string, unknown>;
  result_payload: Record<string, unknown>;
  artifact_path: string | null;
  error_message: string | null;
  run_after: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
};

export type ProjectDetail = {
  project: Project;
  runs: ProjectRun[];
  reports: Report[];
  knowledge_documents: KnowledgeDocument[];
  review_flags: RunReviewFlag[];
};

export type WorkspaceDetail = {
  workspace: Workspace;
  members: WorkspaceMember[];
  projects: Project[];
  pending_invites: WorkspaceInvite[];
  activity: ActivityItem[];
};

export type Analytics = {
  workspace_id: string;
  total_projects: number;
  total_runs: number;
  total_reports: number;
  total_learning_sessions: number;
  total_comments: number;
  total_knowledge_documents: number;
  total_jobs: number;
  checkpoint_pass_rate: number;
  mastery_by_topic: { topic: string; confidence: number; mastered: boolean }[];
  run_volume_by_project: { project_name: string; run_count: number }[];
  report_status_breakdown: { status: string; count: number }[];
  source_quality: { title: string; confidence: number; url: string }[];
  activity_counts: Record<string, number>;
};
