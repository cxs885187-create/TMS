from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ReviewStatus = Literal["草稿", "待审阅", "已确认", "有争议", "已过期"]
ApprovalStatus = Literal["pending", "approved", "rejected"]
SystemMode = Literal["normal", "manual_collaboration", "readonly_protection", "low_confidence"]
WorkflowLoopType = Literal["问题进入", "文献进入", "实验闭环", "写作闭环", "交接闭环", "任务执行闭环"]
ObjectType = Literal["任务", "文献记忆", "实验记录", "讨论记忆", "决策记录", "交接包", "专家声明", "术语条目"]
MemoryType = Literal["文献记忆", "实验记忆", "讨论记忆", "决策记忆", "流程记忆"]
ApprovalObjectType = Literal["memory", "decision", "term", "expertise", "handover", "agent_result", "trust_event"]
OntologyLevel = Literal["team", "project"]
MapView = Literal["person", "topic", "project", "trust"]
WorkflowGateStatus = Literal[
    "waiting_upstream_submission",
    "waiting_downstream_acceptance",
    "waiting_leader_confirmation",
    "rework_required",
    "completed",
    "readonly",
]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Project(BaseModel):
    id: str
    name: str
    owner_user_id: str | None = None
    stage: str
    summary: str = ""
    status: str = "进行中"
    risks: list[str] = Field(default_factory=list)
    research_questions: list[str] = Field(default_factory=list)
    milestones: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class ProjectCreateInput(BaseModel):
    name: str
    content: str

    @field_validator("name", "content")
    @classmethod
    def field_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("字段不能为空")
        return value.strip()


class ProjectSource(BaseModel):
    id: str
    project_id: str
    uploaded_by: str
    source_type: Literal["pdf", "pasted_text", "markdown"]
    title: str
    file_name: str | None = None
    raw_text: str = ""
    status: Literal["uploaded", "structured", "approved"] = "uploaded"
    review_memory_id: str | None = None
    created_at: str = Field(default_factory=now_iso)


class ProjectSourceTextInput(BaseModel):
    title: str = ""
    content: str

    @field_validator("content")
    @classmethod
    def field_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("字段不能为空")
        return value.strip()

    @field_validator("title")
    @classmethod
    def title_may_be_blank(cls, value: str) -> str:
        return value.strip()


class CapabilitySubmission(BaseModel):
    id: str
    project_id: str
    user_id: str
    raw_text: str
    proof_file_refs: list[str] = Field(default_factory=list)
    proof_texts: list[str] = Field(default_factory=list)
    status: Literal["submitted", "structured", "approved"] = "submitted"
    created_at: str = Field(default_factory=now_iso)


class ExpertProfileRecord(BaseModel):
    id: str
    project_id: str
    user_id: str
    structured_capabilities: list[ExpertiseClaim] = Field(default_factory=list)
    proof_refs: list[str] = Field(default_factory=list)
    initial_confidence: float = 0.0
    current_confidence: float = 0.0
    confidence_breakdown: dict[str, float] = Field(default_factory=dict)
    status: Literal["pending_review", "active"] = "pending_review"
    network_node_id: str
    review_memory_ids: list[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=now_iso)


class ExpertRelationRecord(BaseModel):
    id: str
    project_id: str
    from_user_id: str
    to_user_id: str
    relation_type: Literal["can_handoff_to", "can_review", "depends_on", "high_trust", "needs_support_from"]
    weight: float
    evidence_memory_ids: list[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=now_iso)


class User(BaseModel):
    id: str
    name: str
    role: str
    actor_id: str | None = None
    project_ids: list[str] = Field(default_factory=list)
    team_ids: list[str] = Field(default_factory=lambda: ["team-main"])
    permission_profile: str = "standard"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class ProjectMember(BaseModel):
    id: str
    project_id: str
    user_id: str
    role: Literal["leader", "member", "manager"]
    membership_status: Literal["active", "removed"] = "active"
    joined_at: str = Field(default_factory=now_iso)


class ProjectJoinRequest(BaseModel):
    id: str
    project_id: str
    applicant_user_id: str
    message: str = ""
    status: Literal["pending", "approved", "rejected"] = "pending"
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    reject_reason: str = ""
    created_at: str = Field(default_factory=now_iso)


class JoinRequestCreateInput(BaseModel):
    message: str = ""


class JoinRequestRejectInput(BaseModel):
    reason: str = ""


class ExpertiseClaim(BaseModel):
    id: str | None = None
    domain: str
    method: str
    tool: str
    level: str
    evidence: list[str]
    recency: str
    supported_roles: list[str]
    boundaries: str
    self_confidence: float = Field(ge=0, le=1)
    verification_status: str
    peer_confirmations: list[str] = Field(default_factory=list)
    behavioral_evidence: list[str] = Field(default_factory=list)
    outcome_validation: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = "草稿"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class Actor(BaseModel):
    id: str
    name: str
    actor_type: Literal["human", "ai"]
    role: str
    expertise_claims: list[ExpertiseClaim] = Field(default_factory=list)
    trust: dict[str, dict[str, float]] = Field(default_factory=dict)
    availability: str = "可协作"
    affiliation: str = ""
    verified_expertise_profiles: list[str] = Field(default_factory=list)
    contribution_summary: str = ""
    visibility_scope: str = "project"


class Task(BaseModel):
    id: str
    project_id: str
    plan_id: str | None = None
    task_index: int | None = None
    title: str
    task_type: str
    description: str
    status: str
    tags: list[str] = Field(default_factory=list)
    owner_id: str | None = None
    reviewer_user_id: str | None = None
    review_status: ReviewStatus = "草稿"
    next_action: str = ""
    initiator: str | None = None
    recommended_experts: list[str] = Field(default_factory=list)
    predecessor_task_id: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    dependency_ids: list[str] = Field(default_factory=list)
    parallel_group_id: str | None = None
    handoff_requirements: str = ""
    due_at: str | None = None
    outputs: list[str] = Field(default_factory=list)
    required_roles: list[str] = Field(default_factory=list)
    workflow_gate_status: WorkflowGateStatus = "waiting_upstream_submission"
    leader_confirmation_status: Literal["not_required", "pending", "approved", "rejected"] = "not_required"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class MemoryVersionEntry(BaseModel):
    version: int
    summary: str
    next_action_or_implication: str = ""
    updated_by: str
    updated_at: str = Field(default_factory=now_iso)


class MemoryItem(BaseModel):
    id: str
    project_id: str
    memory_layer: Literal["user", "review", "shared", "event"] = "review"
    memory_type: MemoryType | str
    title: str
    summary: str
    source: str
    confidence: str
    review_status: ReviewStatus
    tags: list[str] = Field(default_factory=list)
    linked_evidence: list[str] = Field(default_factory=list)
    linked_decisions: list[str] = Field(default_factory=list)
    shared: bool = False
    owner_user_id: str | None = None
    visible_to_user_ids: list[str] = Field(default_factory=list)
    actors_involved: list[str] = Field(default_factory=list)
    next_action_or_implication: str = ""
    version: int = 1
    version_history: list[MemoryVersionEntry] = Field(default_factory=list)
    conflict_flags: list[str] = Field(default_factory=list)
    source_or_provenance: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class MemoryCreate(BaseModel):
    memory_type: MemoryType | str
    title: str
    summary: str
    source: str
    confidence: str
    tags: list[str] = Field(default_factory=list)
    linked_evidence: list[str] = Field(default_factory=list)
    linked_decisions: list[str] = Field(default_factory=list)
    actors_involved: list[str] = Field(default_factory=list)
    next_action_or_implication: str = ""

    @field_validator("source")
    @classmethod
    def source_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("来源不能为空")
        return value


class MemoryUpdateInput(BaseModel):
    summary: str
    next_action_or_implication: str = ""


class Decision(BaseModel):
    id: str
    project_id: str
    title: str
    decision_body: str
    rationale: str
    approval_status: str
    linked_evidence: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    approvers: list[str] = Field(default_factory=list)
    effective_scope: str = "project"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class Evidence(BaseModel):
    id: str
    project_id: str
    evidence_type: str
    title: str
    source: str
    verification_status: str
    uri_or_file_ref: str = ""
    excerpt: str = ""
    linked_objects: list[str] = Field(default_factory=list)
    created_by: str | None = None


class HandoverBundle(BaseModel):
    id: str
    project_id: str
    summary: str
    key_members: list[str]
    critical_decisions: list[str]
    key_memories: list[str]
    open_questions: list[str]
    risk_items: list[str]
    review_status: ReviewStatus
    generated_from: list[str] = Field(default_factory=list)
    published: bool = False
    created_at: str = Field(default_factory=now_iso)


class PlanTaskDraft(BaseModel):
    task_index: int
    title: str
    goal: str
    assigned_user_id: str
    reviewer_user_id: str
    handoff_requirements: str
    ddl: str
    predecessor_task_id: str | None = None
    dependency_ids: list[str] = Field(default_factory=list)


class PlanRecord(BaseModel):
    id: str
    project_id: str
    version: int
    plan_title: str = ""
    plan_summary: str = ""
    execution_mode: Literal["linear", "dag"] = "linear"
    plan_status: Literal["draft", "leader_editing", "approved", "superseded"] = "draft"
    generated_by_agent_run_id: str
    structured_plan: list[PlanTaskDraft] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    planning_readiness: PlanningReadiness | None = None
    generation_mode: Literal["normal", "forced_risky", "blocked"] = "normal"
    generation_source: Literal["llm_full", "llm_repaired", "capability_skeleton_fallback", "blocked"] = "blocked"
    generation_diagnostics: list[str] = Field(default_factory=list)
    leader_feedback: str = ""
    approved_at: str | None = None
    based_on_memory_ids: list[str] = Field(default_factory=list)
    shared_snapshot_signature: str = ""
    is_stale: bool = False
    stale_reason: str = ""
    created_at: str = Field(default_factory=now_iso)


class PlanRevisionInput(BaseModel):
    leader_feedback: str = ""
    structured_plan: list[PlanTaskDraft] = Field(default_factory=list)


class AgentRunRecord(BaseModel):
    id: str
    project_id: str
    triggered_by: str
    model_name: str
    run_type: str
    status: Literal["running", "completed", "failed"] = "running"
    analysis_output_memory_id: str | None = None
    plan_output_memory_id: str | None = None
    created_at: str = Field(default_factory=now_iso)


class PlanningRunInput(BaseModel):
    force_generate: bool = False


class TaskSubmitInput(BaseModel):
    summary: str
    handoff_note: str


class AcceptanceRecord(BaseModel):
    id: str
    project_id: str
    task_id: str
    submitted_by: str
    accepted_by: str
    decision: Literal["started", "accepted", "rejected"]
    comment: str = ""
    related_user_memory_id: str | None = None
    upstream_task_ids: list[str] = Field(default_factory=list)
    leader_decision: Literal["pending", "approved", "rejected"] | None = None
    leader_comment: str = ""
    leader_confirmed_by: str | None = None
    leader_confirmed_at: str | None = None
    created_at: str = Field(default_factory=now_iso)


class AcceptanceDecisionInput(BaseModel):
    decision: Literal["accepted", "rejected"]
    comment: str = ""


class AssistantQueryInput(BaseModel):
    query: str


class ProjectAssistantSession(BaseModel):
    id: str
    project_id: str
    user_id: str
    query: str
    answer: str
    retrieved_shared_memory_ids: list[str] = Field(default_factory=list)
    shared_context_memory_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class WorkflowStep(BaseModel):
    id: str
    title: str
    status: Literal["待开始", "进行中", "已完成", "受阻"] = "待开始"
    required_output: str


class TMSWorkflow(BaseModel):
    id: str
    project_id: str
    loop_type: WorkflowLoopType
    title: str
    description: str
    related_object_id: str | None = None
    steps: list[WorkflowStep]
    current_state: str = "draft"
    gate_status: WorkflowGateStatus = "readonly"
    current_task_id: str | None = None
    state_message: str = ""
    advance_action_label: str = ""
    allowed_advance_user_ids: list[str] = Field(default_factory=list)


class WorkflowAdvanceInput(BaseModel):
    note: str = ""


class SystemModeUpdate(BaseModel):
    mode: SystemMode
    label: str
    message: str
    llm_available: bool = True
    vector_search_available: bool = True
    async_queue_available: bool = True
    database_writable: bool = True


class SystemState(BaseModel):
    mode: SystemMode
    label: str
    message: str
    llm_available: bool = True
    vector_search_available: bool = True
    async_queue_available: bool = True
    database_writable: bool = True


class AuditEvent(BaseModel):
    id: str
    project_id: str
    action: str
    object_type: str
    object_id: str
    message: str
    actor_id: str | None = None
    created_at: str = Field(default_factory=now_iso)


class LLMConfigInput(BaseModel):
    scope: Literal["personal", "project", "team"]
    provider_name: str
    base_url: str
    api_key: str
    chat_model: str
    embedding_model: str
    temperature: float = Field(ge=0, le=2)
    max_tokens: int = Field(gt=0, le=200000)


class LLMConfigPublic(BaseModel):
    scope: Literal["personal", "project", "team"]
    provider_name: str
    base_url: str
    api_key_masked: str
    chat_model: str
    embedding_model: str
    temperature: float
    max_tokens: int


class LLMEffectiveConfigDiagnostic(BaseModel):
    source: Literal["default_hardcoded", "project_override"]
    enabled: bool
    provider_name: str
    base_url: str
    api_key_masked: str
    chat_model: str
    embedding_model: str
    temperature: float
    max_tokens: int


class LLMAttemptDiagnostic(BaseModel):
    stage: Literal["analysis", "planning", "dispatch", "capability_extraction"]
    status: Literal["success", "failure"]
    diagnostic_code: str
    error_type: str = ""
    message: str = ""
    http_status: int | None = None
    response_excerpt: str = ""
    provider_name: str = ""
    model: str = ""
    config_source: Literal["default_hardcoded", "project_override"] = "default_hardcoded"


class ProjectLLMDiagnostics(BaseModel):
    effective_config: LLMEffectiveConfigDiagnostic
    latest_attempt: LLMAttemptDiagnostic | None = None


class RecommendationCandidate(BaseModel):
    actor_id: str
    actor_name: str
    actor_type: Literal["human", "ai"]
    score: float
    reasons: list[str]
    factor_breakdown: dict[str, float] = Field(default_factory=dict)
    missing_capabilities: list[str] = Field(default_factory=list)


class RecommendationResult(BaseModel):
    mode: Literal["normal", "low_trust_data"]
    primary_expert: RecommendationCandidate | None = None
    secondary_collaborators: list[RecommendationCandidate] = Field(default_factory=list)
    reviewer_candidates: list[RecommendationCandidate] = Field(default_factory=list)
    ai_assistants: list[RecommendationCandidate] = Field(default_factory=list)
    candidates: list[RecommendationCandidate]
    message: str


class TermEntry(BaseModel):
    id: str
    canonical_term: str
    aliases: list[str]
    domain_scope: str
    definition: str
    related_terms: list[str]
    do_not_confuse_with: list[str]
    example_usage: str
    owner: str
    reviewer: str
    level: OntologyLevel
    project_id: str | None = None
    review_status: ReviewStatus = "已确认"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class TermCreateInput(BaseModel):
    canonical_term: str
    aliases: list[str] = Field(default_factory=list)
    domain_scope: str
    definition: str
    related_terms: list[str] = Field(default_factory=list)
    do_not_confuse_with: list[str] = Field(default_factory=list)
    example_usage: str
    owner: str
    reviewer: str
    level: OntologyLevel


class ApprovalItem(BaseModel):
    id: str
    project_id: str
    object_type: ApprovalObjectType
    object_id: str
    title: str
    requested_by: str
    reviewer_role: str
    status: ApprovalStatus = "pending"
    reason: str
    created_at: str = Field(default_factory=now_iso)
    resolved_at: str | None = None
    resolved_by: str | None = None
    resolution_comment: str = ""


class ApprovalDecisionInput(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str = ""


class TrustEventInput(BaseModel):
    target_actor_id: str
    context_domain: str
    event_type: str
    weight: float = Field(gt=0)
    source_object_type: str
    source_object_id: str
    review_status: str


class TrustEvent(BaseModel):
    id: str
    project_id: str
    target_actor_id: str
    context_domain: str
    event_type: str
    weight: float
    review_status: str
    source_object_type: str
    source_object_id: str
    balance_after: float
    created_at: str = Field(default_factory=now_iso)


class TrustRelation(BaseModel):
    actor_id: str
    context_type: str = "domain"
    context_key: str
    alpha: float = 1.0
    beta: float = 1.0
    last_updated_at: str = Field(default_factory=now_iso)
    supporting_events: list[str] = Field(default_factory=list)


class AgentObservation(BaseModel):
    id: str
    project_id: str
    actor_id: str | None = None
    observation_type: str
    title: str
    summary: str
    linked_object_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class StructuredCandidate(BaseModel):
    object_type: ObjectType
    project_id: str
    title: str
    summary: str
    actors_involved: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    method_tags: list[str] = Field(default_factory=list)
    tool_tags: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    confidence: str = "中"
    missing_required_fields: list[str] = Field(default_factory=list)
    review_required: bool = True
    suggested_next_action: str = ""
    status: ReviewStatus = "草稿"


class VectorPayload(BaseModel):
    text: str
    chunk_id: str
    object_type: ObjectType
    object_id: str
    project_id: str
    tags: list[str] = Field(default_factory=list)
    created_by: str
    visibility_scope: str = "project"
    embedding_model: str


class AgentIntakeInput(BaseModel):
    object_type: ObjectType
    raw_input: str
    project_id: str
    force_execute: bool = False


class IntakeReadiness(BaseModel):
    ready: bool
    status: Literal["ready", "risky_but_ingestable", "blocked"] = "ready"
    message: str = ""
    risk_summary: str = ""
    risk_items: list[str] = Field(default_factory=list)
    supplement_materials: list[dict[str, str | None]] = Field(default_factory=list)
    force_execute_allowed: bool = False
    force_executed: bool = False


class AgentIntakeResult(BaseModel):
    structured_candidate: StructuredCandidate
    vector_payloads: list[VectorPayload]
    readiness: IntakeReadiness
    quality_hints: list[str]
    raw_input: str
    prompt_version: str
    model_config_id: str
    created_by: str
    saved_review_memory_id: str | None = None


class ExpertiseMapNode(BaseModel):
    id: str
    type: str
    label: str
    weight: float = 1.0


class ExpertiseMapEdge(BaseModel):
    source: str
    target: str
    type: str
    weight: float = 1.0


class ExpertiseMap(BaseModel):
    view: MapView
    supported_views: list[MapView]
    nodes: list[ExpertiseMapNode]
    edges: list[ExpertiseMapEdge]
    network_status: Literal["pending_profile_approval", "candidate_only", "active"] = "pending_profile_approval"
    message: str = ""


class PlanningReadiness(BaseModel):
    ready: bool
    status: Literal["ready", "risky_but_generatable", "blocked"] = "ready"
    missing_items: list[str] = Field(default_factory=list)
    missing_item_labels: list[str] = Field(default_factory=list)
    satisfied_items: list[str] = Field(default_factory=list)
    message: str = ""
    risk_summary: str = ""
    risk_items: list[str] = Field(default_factory=list)
    supplement_materials: list[dict[str, str]] = Field(default_factory=list)
    force_generate_allowed: bool = False


class SearchResultItem(BaseModel):
    object_type: str
    object_id: str
    title: str
    summary: str
    tags: list[str] = Field(default_factory=list)
    matched_by: str
    review_status: str = "草稿"


class SearchResult(BaseModel):
    mode: Literal["semantic", "keyword_fallback"]
    query: str
    results: list[SearchResultItem]
    message: str
