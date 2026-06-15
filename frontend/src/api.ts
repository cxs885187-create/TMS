import type {
  AcceptanceActionResult,
  AcceptanceDecisionPayload,
  AssistantQueryResult,
  AgentIntakePayload,
  AgentIntakeResult,
  ApprovalDecisionPayload,
  ApprovalItem,
  AuditEvent,
  ExpertiseMap,
  HandoverBundle,
  LLMConfigPayload,
  LLMConfigPublic,
  MemoryCreatePayload,
  MemoryItem,
  PlanningRunResult,
  PlanningRunPayload,
  PlanRecord,
  CapabilitySubmissionResult,
  PlazaProjectCard,
  Project,
  ProjectCreatePayload,
  ProjectJoinRequest,
  ProjectSourceIngestResult,
  ProjectSourceTextPayload,
  RecommendationResult,
  SearchResult,
  SystemModePayload,
  TMSWorkflow,
  Task,
  TaskSubmitPayload,
  TermCreatePayload,
  TermEntry,
  User,
  WorkflowAdvancePayload,
  Workspace,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8011";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const hasFormDataBody = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    headers: hasFormDataBody
      ? init?.headers
      : {
          "Content-Type": "application/json",
          ...init?.headers,
        },
    ...init,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `请求失败：${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function fetchWorkspace(projectId: string): Promise<Workspace> {
  return request<Workspace>(`/api/projects/${projectId}/workspace`);
}

export function fetchUsers(): Promise<{ users: User[] }> {
  return request<{ users: User[] }>("/api/users");
}

export function fetchPlaza(userId: string): Promise<{ current_user: User; projects: PlazaProjectCard[] }> {
  return request<{ current_user: User; projects: PlazaProjectCard[] }>(`/api/users/${userId}/plaza`);
}

export function createProject(userId: string, payload: ProjectCreatePayload): Promise<Project> {
  return request<Project>(`/api/users/${userId}/projects`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createProjectSourceText(
  userId: string,
  projectId: string,
  payload: ProjectSourceTextPayload,
): Promise<ProjectSourceIngestResult> {
  return request<ProjectSourceIngestResult>(`/api/users/${userId}/projects/${projectId}/project-sources/text`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function uploadProjectSourcePdf(userId: string, projectId: string, file: File): Promise<ProjectSourceIngestResult> {
  const formData = new FormData();
  formData.append("file", file);
  return request<ProjectSourceIngestResult>(`/api/users/${userId}/projects/${projectId}/project-sources/pdf`, {
    method: "POST",
    body: formData,
  });
}

export function uploadProjectSourceMarkdown(userId: string, projectId: string, file: File): Promise<ProjectSourceIngestResult> {
  const formData = new FormData();
  formData.append("file", file);
  return request<ProjectSourceIngestResult>(`/api/users/${userId}/projects/${projectId}/project-sources/markdown`, {
    method: "POST",
    body: formData,
  });
}

export function submitCapability(userId: string, projectId: string, rawText: string, proofFile?: File | null): Promise<CapabilitySubmissionResult> {
  const formData = new FormData();
  formData.append("raw_text", rawText);
  if (proofFile) {
    formData.append("proof_file", proofFile);
  }
  return request<CapabilitySubmissionResult>(`/api/users/${userId}/projects/${projectId}/capability-submissions`, {
    method: "POST",
    body: formData,
  });
}

export function runPlanningAgent(userId: string, projectId: string, payload: PlanningRunPayload = {}): Promise<PlanningRunResult> {
  return request<PlanningRunResult>(`/api/users/${userId}/projects/${projectId}/agent-runs`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function approvePlan(userId: string, projectId: string, planId: string, comment: string): Promise<{ plan: PlanRecord; tasks: Task[]; plan_memory: MemoryItem }> {
  return request<{ plan: PlanRecord; tasks: Task[]; plan_memory: MemoryItem }>(`/api/users/${userId}/projects/${projectId}/plans/${planId}/approve`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

export function revisePlan(
  userId: string,
  projectId: string,
  planId: string,
  payload: { leader_feedback: string; structured_plan: PlanRecord["structured_plan"] },
): Promise<PlanRecord> {
  return request<PlanRecord>(`/api/users/${userId}/projects/${projectId}/plans/${planId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function regeneratePlan(userId: string, projectId: string, planId: string): Promise<PlanningRunResult> {
  return request<PlanningRunResult>(`/api/users/${userId}/projects/${projectId}/plans/${planId}/regenerate`, {
    method: "POST",
  });
}

export function submitTaskResult(
  userId: string,
  projectId: string,
  taskId: string,
  payload: TaskSubmitPayload,
  resultFile?: File | null,
): Promise<AcceptanceActionResult> {
  if (resultFile) {
    const formData = new FormData();
    formData.append("summary", payload.summary);
    formData.append("handoff_note", payload.handoff_note);
    formData.append("result_file", resultFile);
    return request<AcceptanceActionResult>(`/api/users/${userId}/projects/${projectId}/tasks/${taskId}/submit`, {
      method: "POST",
      body: formData,
    });
  }
  return request<AcceptanceActionResult>(`/api/users/${userId}/projects/${projectId}/tasks/${taskId}/submit`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function startAcceptance(userId: string, projectId: string, taskId: string): Promise<AcceptanceActionResult> {
  return request<AcceptanceActionResult>(`/api/users/${userId}/projects/${projectId}/tasks/${taskId}/acceptance/start`, {
    method: "POST",
  });
}

export function decideAcceptance(
  userId: string,
  projectId: string,
  taskId: string,
  payload: AcceptanceDecisionPayload,
): Promise<AcceptanceActionResult> {
  return request<AcceptanceActionResult>(`/api/users/${userId}/projects/${projectId}/tasks/${taskId}/acceptance/decide`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function queryProjectAssistant(userId: string, projectId: string, query: string): Promise<AssistantQueryResult> {
  return request<AssistantQueryResult>(`/api/users/${userId}/projects/${projectId}/assistant/query`, {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

export function createJoinRequest(userId: string, projectId: string, message: string): Promise<ProjectJoinRequest> {
  return request<ProjectJoinRequest>(`/api/users/${userId}/projects/${projectId}/join-requests`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function approveJoinRequest(userId: string, projectId: string, requestId: string): Promise<ProjectJoinRequest> {
  return request<ProjectJoinRequest>(`/api/users/${userId}/projects/${projectId}/join-requests/${requestId}/approve`, {
    method: "POST",
  });
}

export function rejectJoinRequest(
  userId: string,
  projectId: string,
  requestId: string,
  reason: string,
): Promise<ProjectJoinRequest> {
  return request<ProjectJoinRequest>(`/api/users/${userId}/projects/${projectId}/join-requests/${requestId}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function fetchProjects(): Promise<{ projects: Project[] }> {
  return request<{ projects: Project[] }>("/api/projects");
}

export function fetchUserProjects(userId: string): Promise<{ current_user: User; projects: Project[] }> {
  return request<{ current_user: User; projects: Project[] }>(`/api/users/${userId}/projects`);
}

export function fetchUserWorkspace(userId: string, projectId: string): Promise<Workspace> {
  return request<Workspace>(`/api/users/${userId}/projects/${projectId}/workspace`);
}

export function fetchRecommendations(projectId: string, taskId: string): Promise<RecommendationResult> {
  return request<RecommendationResult>(`/api/projects/${projectId}/tasks/${taskId}/recommendations`, {
    method: "POST",
  });
}

export function saveLLMConfig(projectId: string, payload: LLMConfigPayload): Promise<LLMConfigPublic> {
  return request<LLMConfigPublic>(`/api/projects/${projectId}/llm-config`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function createMemory(projectId: string, payload: MemoryCreatePayload): Promise<MemoryItem> {
  return request<MemoryItem>(`/api/projects/${projectId}/memories`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function generateHandover(projectId: string): Promise<HandoverBundle> {
  return request<HandoverBundle>(`/api/projects/${projectId}/handover`, {
    method: "POST",
  });
}

export function setSystemMode(projectId: string, payload: SystemModePayload): Promise<SystemModePayload> {
  return request<SystemModePayload>(`/api/projects/${projectId}/system-mode`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function fetchAuditLog(projectId: string): Promise<{ events: AuditEvent[] }> {
  return request<{ events: AuditEvent[] }>(`/api/projects/${projectId}/audit-log`);
}

export function fetchTerms(userId: string, projectId: string, query = ""): Promise<{ entries: TermEntry[] }> {
  const suffix = query ? `?q=${encodeURIComponent(query)}` : "";
  return request<{ entries: TermEntry[] }>(`/api/users/${userId}/projects/${projectId}/terms${suffix}`);
}

export function createTerm(userId: string, projectId: string, payload: TermCreatePayload): Promise<TermEntry> {
  return request<TermEntry>(`/api/users/${userId}/projects/${projectId}/terms`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchApprovals(userId: string, projectId: string): Promise<{ items: ApprovalItem[] }> {
  return request<{ items: ApprovalItem[] }>(`/api/users/${userId}/projects/${projectId}/approvals`);
}

export function decideApproval(
  userId: string,
  projectId: string,
  approvalId: string,
  payload: ApprovalDecisionPayload,
): Promise<ApprovalItem> {
  return request<ApprovalItem>(`/api/users/${userId}/projects/${projectId}/approvals/${approvalId}/decide`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runAgentIntake(userId: string, projectId: string, payload: AgentIntakePayload): Promise<AgentIntakeResult> {
  return request<AgentIntakeResult>(`/api/users/${userId}/projects/${projectId}/agent-intake`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchExpertiseMap(
  userId: string,
  projectId: string,
  view: "person" | "topic" | "project" | "trust" = "person",
): Promise<ExpertiseMap> {
  return request<ExpertiseMap>(`/api/users/${userId}/projects/${projectId}/expertise-map?view=${view}`);
}

export function searchProject(userId: string, projectId: string, query: string): Promise<SearchResult> {
  return request<SearchResult>(`/api/users/${userId}/projects/${projectId}/search?q=${encodeURIComponent(query)}`);
}

export function advanceWorkflow(
  userId: string,
  projectId: string,
  workflowId: string,
  payload: WorkflowAdvancePayload,
): Promise<TMSWorkflow> {
  return request<TMSWorkflow>(`/api/users/${userId}/projects/${projectId}/workflows/${workflowId}/advance`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
