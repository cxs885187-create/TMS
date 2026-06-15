export type Project = {
  id: string;
  name: string;
  owner_user_id?: string | null;
  stage: string;
  summary: string;
  status: string;
  risks: string[];
};

export type ProjectCreatePayload = {
  name: string;
  content: string;
};

export type ProjectJoinRequest = {
  id: string;
  project_id: string;
  applicant_user_id: string;
  message: string;
  status: "pending" | "approved" | "rejected";
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  reject_reason: string;
  created_at?: string;
};

export type ProjectSourceTextPayload = {
  title: string;
  content: string;
};

export type ProjectSourceIngestResult = {
  id: string;
  project_id: string;
  uploaded_by: string;
  source_type: "pdf" | "pasted_text" | "markdown";
  title: string;
  file_name?: string | null;
  status: string;
  review_memory: MemoryItem;
};

export type CapabilitySubmissionResult = {
  submission: {
    id: string;
    project_id: string;
    user_id: string;
    raw_text: string;
    proof_file_refs: string[];
    status: string;
  };
  expert_profile: ExpertProfile;
  review_memories: MemoryItem[];
  review_memory_ids: string[];
  relation_snapshot: Array<{
    id: string;
    from_user_id: string;
    to_user_id: string;
    relation_type: string;
    weight: number;
  }>;
};

export type PlazaProjectCard = {
  id: string;
  name: string;
  summary: string;
  stage: string;
  owner_user_id?: string | null;
  member_count: number;
  membership_state: "none" | "requested" | "member";
  pending_join_requests: Array<{
    id: string;
    applicant_user_id: string;
    message: string;
    created_at: string;
  }>;
};

export type User = {
  id: string;
  name: string;
  role: string;
  actor_id?: string | null;
  project_ids: string[];
};

export type ExpertiseClaim = {
  domain: string;
  method: string;
  tool: string;
  level: string;
  evidence: string[];
  recency: string;
  supported_roles: string[];
  boundaries: string;
  self_confidence: number;
  verification_status: string;
};

export type Actor = {
  id: string;
  name: string;
  actor_type: "human" | "ai";
  role: string;
  expertise_claims: ExpertiseClaim[];
  availability: string;
  contribution_summary?: string;
};

export type ExpertProfile = {
  id: string;
  project_id: string;
  user_id: string;
  structured_capabilities: ExpertiseClaim[];
  proof_refs: string[];
  initial_confidence: number;
  current_confidence: number;
  confidence_breakdown: Record<string, number>;
  status: "pending_review" | "active";
  network_node_id: string;
  review_memory_ids: string[];
};

export type ExpertRelation = {
  id: string;
  project_id: string;
  from_user_id: string;
  to_user_id: string;
  relation_type: "can_handoff_to" | "can_review" | "depends_on" | "high_trust" | "needs_support_from";
  weight: number;
  evidence_memory_ids: string[];
};

export type Task = {
  id: string;
  project_id: string;
  plan_id?: string | null;
  task_index?: number | null;
  title: string;
  task_type: string;
  description: string;
  status: string;
  tags: string[];
  owner_id?: string | null;
  reviewer_user_id?: string | null;
  review_status: string;
  next_action: string;
  predecessor_task_id?: string | null;
  dependency_ids?: string[];
  parallel_group_id?: string | null;
  handoff_requirements?: string;
  outputs?: string[];
  due_at?: string | null;
  workflow_gate_status?:
    | "waiting_upstream_submission"
    | "waiting_downstream_acceptance"
    | "waiting_leader_confirmation"
    | "rework_required"
    | "completed"
    | "readonly";
  leader_confirmation_status?: "not_required" | "pending" | "approved" | "rejected";
};

export type MemoryItem = {
  id: string;
  project_id: string;
  memory_type: string;
  title: string;
  summary: string;
  source: string;
  confidence: string;
  review_status: string;
  tags: string[];
  linked_evidence: string[];
  linked_decisions?: string[];
  shared: boolean;
  actors_involved?: string[];
  next_action_or_implication?: string;
  version: number;
  version_history: Array<{
    version: number;
    summary: string;
    next_action_or_implication: string;
    updated_by: string;
    updated_at: string;
  }>;
};

export type Decision = {
  id: string;
  project_id: string;
  title: string;
  decision_body: string;
  rationale: string;
  approval_status: string;
  linked_evidence: string[];
  risk_notes: string[];
};

export type Evidence = {
  id: string;
  project_id: string;
  evidence_type: string;
  title: string;
  source: string;
  verification_status: string;
};

export type WorkflowStep = {
  id: string;
  title: string;
  status: "待开始" | "进行中" | "已完成" | "受阻";
  required_output: string;
};

export type TMSWorkflow = {
  id: string;
  project_id: string;
  loop_type: "问题进入" | "文献进入" | "实验闭环" | "写作闭环" | "交接闭环" | "任务执行闭环";
  title: string;
  description: string;
  related_object_id?: string | null;
  steps: WorkflowStep[];
  current_state?: string;
  gate_status?:
    | "waiting_upstream_submission"
    | "waiting_downstream_acceptance"
    | "waiting_leader_confirmation"
    | "rework_required"
    | "completed"
    | "readonly";
  current_task_id?: string | null;
  state_message?: string;
  advance_action_label?: string;
  allowed_advance_user_ids?: string[];
};

export type LLMAttemptDiagnostic = {
  stage: "analysis" | "planning" | "dispatch" | "capability_extraction";
  status: "success" | "failure";
  diagnostic_code: string;
  error_type: string;
  message: string;
  http_status?: number | null;
  response_excerpt: string;
  provider_name: string;
  model: string;
  config_source: "default_hardcoded" | "project_override";
};

export type ProjectLLMDiagnostics = {
  effective_config: {
    source: "default_hardcoded" | "project_override";
    enabled: boolean;
    provider_name: string;
    base_url: string;
    api_key_masked: string;
    chat_model: string;
    embedding_model: string;
    temperature: number;
    max_tokens: number;
  };
  latest_attempt?: LLMAttemptDiagnostic | null;
};

export type Workspace = {
  current_user?: User;
  is_project_leader?: boolean;
  current_user_project_role?: "leader" | "member" | "manager" | null;
  project: Project;
  actors: Actor[];
  expert_profiles: ExpertProfile[];
  expert_relations: ExpertRelation[];
  tasks: Task[];
  memories: MemoryItem[];
  decisions: Decision[];
  evidence: Evidence[];
  workflows: TMSWorkflow[];
  terms: TermEntry[];
  approvals: ApprovalItem[];
  plans: PlanRecord[];
  handover_bundles: HandoverBundle[];
  llm_diagnostics?: ProjectLLMDiagnostics;
  system_state: {
    mode: string;
    label: string;
    message: string;
    llm_available?: boolean;
    vector_search_available?: boolean;
    async_queue_available?: boolean;
    database_writable?: boolean;
  };
};

export type WorkflowAdvancePayload = {
  note: string;
};

export type MemoryCreatePayload = {
  memory_type: string;
  title: string;
  summary: string;
  source: string;
  confidence: string;
  tags: string[];
  linked_evidence: string[];
};

export type HandoverBundle = {
  id: string;
  project_id: string;
  summary: string;
  key_members: string[];
  critical_decisions: string[];
  key_memories: string[];
  open_questions: string[];
  risk_items: string[];
  review_status: string;
};

export type SystemModePayload = {
  mode: "normal" | "manual_collaboration" | "readonly_protection" | "low_confidence";
  label: string;
  message: string;
  llm_available?: boolean;
  vector_search_available?: boolean;
  async_queue_available?: boolean;
  database_writable?: boolean;
};

export type AuditEvent = {
  id: string;
  project_id: string;
  action: string;
  object_type: string;
  object_id: string;
  message: string;
};

export type RecommendationCandidate = {
  actor_id: string;
  actor_name: string;
  actor_type: "human" | "ai";
  score: number;
  reasons: string[];
};

export type RecommendationResult = {
  mode: "normal" | "low_trust_data";
  primary_expert: RecommendationCandidate | null;
  candidates: RecommendationCandidate[];
  message: string;
};

export type LLMConfigPayload = {
  scope: "personal" | "project" | "team";
  provider_name: string;
  base_url: string;
  api_key: string;
  chat_model: string;
  embedding_model: string;
  temperature: number;
  max_tokens: number;
};

export type LLMConfigPublic = Omit<LLMConfigPayload, "api_key"> & {
  api_key_masked: string;
};

export type TermEntry = {
  id: string;
  canonical_term: string;
  aliases: string[];
  domain_scope: string;
  definition: string;
  related_terms: string[];
  do_not_confuse_with: string[];
  example_usage: string;
  owner: string;
  reviewer: string;
  level: "team" | "project";
  project_id?: string | null;
  review_status: string;
};

export type TermCreatePayload = {
  canonical_term: string;
  aliases: string[];
  domain_scope: string;
  definition: string;
  related_terms: string[];
  do_not_confuse_with: string[];
  example_usage: string;
  owner: string;
  reviewer: string;
  level: "team" | "project";
};

export type ApprovalItem = {
  id: string;
  project_id: string;
  object_type: "memory" | "decision" | "term" | "expertise" | "handover" | "agent_result" | "trust_event";
  object_id: string;
  title: string;
  requested_by: string;
  reviewer_role: string;
  status: "pending" | "approved" | "rejected";
  reason: string;
  resolution_comment: string;
};

export type ApprovalDecisionPayload = {
  decision: "approved" | "rejected";
  comment: string;
};

export type AgentIntakePayload = {
  object_type: "任务" | "文献记忆" | "实验记录" | "讨论记忆" | "决策记录" | "交接包" | "专家声明" | "术语条目";
  raw_input: string;
  project_id: string;
  force_execute?: boolean;
};

export type AgentIntakeStructuredCandidate = {
  object_type: string;
  project_id: string;
  title: string;
  summary: string;
  actors_involved: string[];
  domain_tags: string[];
  method_tags: string[];
  tool_tags: string[];
  source_refs: string[];
  confidence: string;
  missing_required_fields: string[];
  review_required: boolean;
  suggested_next_action: string;
  status: string;
};

export type VectorPayload = {
  text: string;
  chunk_id: string;
  object_type: string;
  object_id: string;
  project_id: string;
  tags: string[];
  created_by: string;
  visibility_scope: string;
  embedding_model: string;
};

export type AgentIntakeResult = {
  structured_candidate: AgentIntakeStructuredCandidate;
  vector_payloads: VectorPayload[];
  readiness: {
    ready: boolean;
    status: "ready" | "risky_but_ingestable" | "blocked";
    message: string;
    risk_summary: string;
    risk_items: string[];
    supplement_materials: Array<{
      item_key: string;
      label: string;
      why_needed: string;
      recommended_action: string;
      material_id?: string | null;
    }>;
    force_execute_allowed: boolean;
    force_executed: boolean;
  };
  quality_hints: string[];
  raw_input: string;
  prompt_version: string;
  model_config_id: string;
  created_by: string;
  saved_review_memory_id?: string | null;
};

export type ExpertiseMapNode = {
  id: string;
  type: string;
  label: string;
  weight: number;
};

export type ExpertiseMapEdge = {
  source: string;
  target: string;
  type: string;
  weight: number;
};

export type ExpertiseMap = {
  view: "person" | "topic" | "project" | "trust";
  supported_views: Array<"person" | "topic" | "project" | "trust">;
  nodes: ExpertiseMapNode[];
  edges: ExpertiseMapEdge[];
  network_status: "pending_profile_approval" | "candidate_only" | "active";
  message: string;
};

export type SearchResultItem = {
  object_type: string;
  object_id: string;
  title: string;
  summary: string;
  tags: string[];
  matched_by: string;
  review_status: string;
};

export type SearchResult = {
  mode: "semantic" | "keyword_fallback";
  query: string;
  results: SearchResultItem[];
  message: string;
};

export type PlanTaskDraft = {
  task_index: number;
  title: string;
  goal: string;
  assigned_user_id: string;
  reviewer_user_id: string;
  handoff_requirements: string;
  ddl: string;
  predecessor_task_id?: string | null;
  dependency_ids: string[];
};

export type PlanRecord = {
  id: string;
  project_id: string;
  version: number;
  plan_title: string;
  plan_summary: string;
  execution_mode?: "linear" | "dag";
  plan_status: "draft" | "leader_editing" | "approved" | "superseded";
  generated_by_agent_run_id: string;
  structured_plan: PlanTaskDraft[];
  risk_notes: string[];
  planning_readiness?: {
    ready: boolean;
    status: "ready" | "risky_but_generatable" | "blocked";
    missing_items: string[];
    missing_item_labels: string[];
    satisfied_items: string[];
    message: string;
    risk_summary: string;
    risk_items: string[];
    supplement_materials: Array<{
      item_key: string;
      label: string;
      why_needed: string;
      recommended_action: string;
    }>;
    force_generate_allowed: boolean;
  } | null;
  generation_mode?: "normal" | "forced_risky" | "blocked";
  generation_source?: "llm_full" | "llm_repaired" | "capability_skeleton_fallback" | "blocked";
  generation_diagnostics?: string[];
  leader_feedback: string;
  approved_at?: string | null;
  based_on_memory_ids?: string[];
  shared_snapshot_signature?: string;
  is_stale?: boolean;
  stale_reason?: string;
  created_at: string;
};

export type AgentRunRecord = {
  id: string;
  project_id: string;
  triggered_by: string;
  model_name: string;
  run_type: string;
  status: "running" | "completed" | "failed";
  analysis_output_memory_id?: string | null;
  plan_output_memory_id?: string | null;
  created_at: string;
};

export type PlanningRunResult = {
  agent_run: AgentRunRecord;
  analysis_memory: MemoryItem;
  plan_memory: MemoryItem;
  plan: PlanRecord;
};

export type PlanningRunPayload = {
  force_generate?: boolean;
};

export type TaskSubmitPayload = {
  summary: string;
  handoff_note: string;
};

export type AcceptanceDecisionPayload = {
  decision: "accepted" | "rejected";
  comment: string;
};

export type AcceptanceActionResult = {
  task?: Task;
  previous_task?: Task;
  current_task?: Task;
  submission_memory?: MemoryItem;
  handoff_memory?: MemoryItem;
  rejection_memory?: MemoryItem;
  acceptance_record?: {
    id: string;
    project_id: string;
    task_id: string;
    submitted_by: string;
    accepted_by: string;
    decision: "started" | "accepted" | "rejected";
    comment: string;
    related_user_memory_id?: string | null;
    leader_decision?: "pending" | "approved" | "rejected" | null;
    created_at: string;
  };
};

export type AssistantQueryResult = {
  id: string;
  project_id: string;
  user_id: string;
  query: string;
  answer: string;
  retrieved_shared_memory_ids: string[];
  shared_context_memory_ids?: string[];
  created_at: string;
};
