import {
  AlertTriangle,
  Bot,
  Brain,
  CheckCircle2,
  ClipboardCheck,
  ClipboardList,
  FilePlus2,
  FlaskConical,
  History,
  KeyRound,
  Link2,
  Loader2,
  LogOut,
  Network,
  PanelRightOpen,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  advanceWorkflow,
  approveJoinRequest,
  createMemory,
  createJoinRequest,
  createProject,
  createProjectSourceText,
  createTerm,
  approvePlan,
  decideApproval,
  decideAcceptance,
  fetchApprovals,
  fetchAuditLog,
  fetchExpertiseMap,
  fetchPlaza,
  fetchRecommendations,
  fetchTerms,
  fetchUserProjects,
  fetchUsers,
  fetchUserWorkspace,
  generateHandover,
  queryProjectAssistant,
  regeneratePlan,
  rejectJoinRequest,
  revisePlan,
  runPlanningAgent,
  runAgentIntake,
  saveLLMConfig,
  setSystemMode,
  startAcceptance,
  submitTaskResult,
  submitCapability,
  uploadProjectSourceMarkdown,
  uploadProjectSourcePdf,
} from "./api";
import { ExpertiseMapGraph } from "./expertiseMapGraph";
import {
  AgentIntakePanel,
  Backdrop,
  DetailView,
  EmptyState,
  GlobalStatusBanner,
  HandoverPanel,
  LabeledInput,
  LabeledTextarea,
  LoginScreen,
  PlanningPanel,
  PlazaScreen,
  ProjectAssistantPanel,
  RecommendationPanel,
} from "./components/panels";
import {
  ActorCard,
  DecisionCard,
  HandoverCard,
  MemoryCard,
  TaskCard,
  WorkflowCard,
} from "./components/cards";
import type {
  Actor,
  AcceptanceDecisionPayload,
  AssistantQueryResult,
  AgentIntakePayload,
  AgentIntakeResult,
  AcceptanceActionResult,
  ApprovalItem,
  AuditEvent,
  Decision,
  ExpertiseMap,
  HandoverBundle,
  LLMConfigPayload,
  MemoryCreatePayload,
  MemoryItem,
  PlanningRunResult,
  PlazaProjectCard,
  Project,
  ProjectCreatePayload,
  ProjectSourceTextPayload,
  RecommendationResult,
  Task,
  TaskSubmitPayload,
  TermCreatePayload,
  TermEntry,
  TMSWorkflow,
  User,
  Workspace,
} from "./types";

const navigationItems = [
  { id: "overview", label: "项目总览", icon: PanelRightOpen },
  { id: "tasks", label: "任务与实验", icon: FlaskConical },
  { id: "memories", label: "团队记忆", icon: History },
  { id: "experts", label: "专家网络", icon: Network },
  { id: "governance", label: "术语与治理", icon: ClipboardCheck },
  { id: "decisions", label: "决策与交接", icon: CheckCircle2 },
] as const;

const expertiseMapViewLabels: Record<ExpertiseMap["view"], string> = {
  person: "人物视图",
  topic: "主题视图",
  project: "项目视图",
  trust: "信任视图",
};

type NavigationSectionId = (typeof navigationItems)[number]["id"];

const workspaceSectionMeta: Record<
  NavigationSectionId,
  { title: string; description: string }
> = {
  overview: {
    title: "项目总览",
    description: "聚焦项目状态、风险提醒和下一步动作。",
  },
  tasks: {
    title: "任务与实验",
    description: "推进任务链、闭环流程和验收动作。",
  },
  memories: {
    title: "团队记忆",
    description: "查看、沉淀和审核结构化记忆。",
  },
  experts: {
    title: "专家网络",
    description: "理解成员专长、关系网络和推荐依据。",
  },
  governance: {
    title: "术语与治理",
    description: "统一术语、计划治理和审批队列。",
  },
  decisions: {
    title: "决策与交接",
    description: "沉淀关键决策、交接上下文和审计线索。",
  },
};

type SelectedObject =
  | { kind: "task"; item: Task }
  | { kind: "memory"; item: MemoryItem }
  | { kind: "decision"; item: Decision }
  | { kind: "actor"; item: Actor }
  | { kind: "workflow"; item: TMSWorkflow }
  | { kind: "term"; item: TermEntry }
  | { kind: "approval"; item: ApprovalItem }
  | { kind: "handover"; item: HandoverBundle };

const defaultLLMConfig: LLMConfigPayload = {
  scope: "project",
  provider_name: "深度求索 V4 Pro",
  base_url: "https://api.deepseek.com/v1",
  api_key: "",
  chat_model: "deepseek-v4-pro",
  embedding_model: "deepseek-embedding",
  temperature: 0.3,
  max_tokens: 1200,
};

const defaultMemoryForm: MemoryCreatePayload = {
  memory_type: "讨论记忆",
  title: "",
  summary: "",
  source: "",
  confidence: "中",
  tags: [],
  linked_evidence: [],
};

const defaultTermForm: TermCreatePayload = {
  canonical_term: "",
  aliases: [],
  domain_scope: "",
  definition: "",
  related_terms: [],
  do_not_confuse_with: [],
  example_usage: "",
  owner: "",
  reviewer: "",
  level: "project",
};

const defaultAgentIntake: AgentIntakePayload = {
  object_type: "文献记忆",
  raw_input: "",
  project_id: "",
};

const defaultProjectCreateForm: ProjectCreatePayload = {
  name: "",
  content: "",
};

const defaultProjectSourceTextForm: ProjectSourceTextPayload = {
  title: "",
  content: "",
};

const defaultCapabilityForm = {
  rawText: "",
};

const defaultTaskSubmitForm: TaskSubmitPayload = {
  summary: "",
  handoff_note: "",
};

const defaultAcceptanceDecisionForm: AcceptanceDecisionPayload = {
  decision: "accepted",
  comment: "",
};

export function App() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [plazaProjects, setPlazaProjects] = useState<PlazaProjectCard[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [screen, setScreen] = useState<"plaza" | "workspace">("plaza");
  const [selected, setSelected] = useState<SelectedObject | null>(null);
  const [recommendation, setRecommendation] = useState<RecommendationResult | null>(null);
  const [recommendationTaskId, setRecommendationTaskId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [recommendingTaskId, setRecommendingTaskId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [configOpen, setConfigOpen] = useState(false);
  const [memoryFormOpen, setMemoryFormOpen] = useState(false);
  const [termFormOpen, setTermFormOpen] = useState(false);
  const [agentIntakeOpen, setAgentIntakeOpen] = useState(false);
  const [projectCreateOpen, setProjectCreateOpen] = useState(false);
  const [projectSourceOpen, setProjectSourceOpen] = useState(false);
  const [capabilityOpen, setCapabilityOpen] = useState(false);
  const [taskSubmitOpen, setTaskSubmitOpen] = useState(false);
  const [acceptanceOpen, setAcceptanceOpen] = useState(false);
  const [planEditOpen, setPlanEditOpen] = useState(false);
  const [memoryForm, setMemoryForm] = useState<MemoryCreatePayload>(defaultMemoryForm);
  const [termForm, setTermForm] = useState<TermCreatePayload>(defaultTermForm);
  const [agentIntakeForm, setAgentIntakeForm] = useState<AgentIntakePayload>(defaultAgentIntake);
  const [projectCreateForm, setProjectCreateForm] = useState<ProjectCreatePayload>(defaultProjectCreateForm);
  const [projectSourceTextForm, setProjectSourceTextForm] = useState<ProjectSourceTextPayload>(defaultProjectSourceTextForm);
  const [projectSourceFile, setProjectSourceFile] = useState<File | null>(null);
  const [capabilityForm, setCapabilityForm] = useState(defaultCapabilityForm);
  const [capabilityProofFile, setCapabilityProofFile] = useState<File | null>(null);
  const [taskSubmitForm, setTaskSubmitForm] = useState<TaskSubmitPayload>(defaultTaskSubmitForm);
  const [taskResultFile, setTaskResultFile] = useState<File | null>(null);
  const [acceptanceDecisionForm, setAcceptanceDecisionForm] = useState<AcceptanceDecisionPayload>(defaultAcceptanceDecisionForm);
  const [taskDraftResult, setTaskDraftResult] = useState<{ planId: string; tasks: Task[] } | null>(null);
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [handover, setHandover] = useState<HandoverBundle | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [actionStatus, setActionStatus] = useState("");
  const [llmConfig, setLLMConfig] = useState<LLMConfigPayload>(defaultLLMConfig);
  const [configStatus, setConfigStatus] = useState<string>("未保存");
  const [activeSection, setActiveSection] = useState<NavigationSectionId>("overview");
  const [terms, setTerms] = useState<TermEntry[]>([]);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [expertiseMap, setExpertiseMap] = useState<ExpertiseMap | null>(null);
  const [expertiseMapView, setExpertiseMapView] = useState<ExpertiseMap["view"]>("person");
  const [agentIntakeResult, setAgentIntakeResult] = useState<AgentIntakeResult | null>(null);
  const [planningResult, setPlanningResult] = useState<PlanningRunResult | null>(null);
  const [assistantQuery, setAssistantQuery] = useState("");
  const [assistantResult, setAssistantResult] = useState<AssistantQueryResult | null>(null);
  const [planEditText, setPlanEditText] = useState("");
  const [planEditFeedback, setPlanEditFeedback] = useState("");
  const [planningBusyLabel, setPlanningBusyLabel] = useState("");
  const [isPlanningBusy, setIsPlanningBusy] = useState(false);
  const [isAgentIntakeBusy, setIsAgentIntakeBusy] = useState(false);
  const [isAssistantBusy, setIsAssistantBusy] = useState(false);

  useEffect(() => {
    fetchUsers()
      .then((data) => setUsers(data.users))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!currentUser || !projectId || screen !== "workspace") return;

    setLoading(true);
    setRecommendation(null);
    setRecommendationTaskId(null);
    setAssistantQuery("");
    setAssistantResult(null);
    fetchUserWorkspace(currentUser.id, projectId)
      .then((data) => {
        setWorkspace(data);
        setTerms(data.terms);
        setApprovals(data.approvals);
        if (!planningResult) {
          const pendingPlan = [...data.plans]
            .filter((plan) => plan.plan_status === "draft" || plan.plan_status === "leader_editing")
            .sort((a, b) => b.version - a.version)[0];
          if (pendingPlan) {
            const relatedPlanMemory =
              data.memories.find((memory) => memory.memory_type === "plan_draft" && memory.title.includes(`v${pendingPlan.version}`)) ?? data.memories[0];
            const relatedAnalysisMemory =
              data.memories.find((memory) => memory.title.includes("分析结果草稿")) ?? relatedPlanMemory;
            if (relatedPlanMemory && relatedAnalysisMemory) {
              setPlanningResult({
                agent_run: {
                  id: pendingPlan.generated_by_agent_run_id,
                  project_id: pendingPlan.project_id,
                  triggered_by: data.project.owner_user_id ?? currentUser.id,
                  model_name: "深度求索 V4 Pro",
                  run_type: "project_bootstrap_or_replan",
                  status: "completed",
                  analysis_output_memory_id: relatedAnalysisMemory.id,
                  plan_output_memory_id: relatedPlanMemory.id,
                  created_at: pendingPlan.created_at,
                },
                analysis_memory: relatedAnalysisMemory,
                plan_memory: relatedPlanMemory,
                plan: pendingPlan,
              });
              setPlanEditText(JSON.stringify(pendingPlan.structured_plan, null, 2));
            }
          }
        }
        setSelected(data.tasks[0] ? { kind: "task", item: data.tasks[0] } : null);
        setAgentIntakeForm((prev) => ({ ...prev, project_id: projectId }));
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [currentUser, projectId]);

  useEffect(() => {
    if (!currentUser || !projectId || screen !== "workspace") return;
    void refreshSidebarData();
  }, [currentUser, projectId, screen, workspace?.system_state.mode, expertiseMapView]);

  async function refreshPlaza() {
    if (!currentUser) return;
    const [plaza, userProjects] = await Promise.all([
      fetchPlaza(currentUser.id),
      fetchUserProjects(currentUser.id),
    ]);
    setPlazaProjects(plaza.projects);
    setProjects(userProjects.projects);
  }

  async function refreshSidebarData() {
    if (!currentUser || !projectId) return;
    const [audit, termsResult, approvalsResult, mapResult] = await Promise.all([
      fetchAuditLog(projectId).catch(() => ({ events: [] })),
      fetchTerms(currentUser.id, projectId).catch(() => ({ entries: [] })),
      fetchApprovals(currentUser.id, projectId).catch(() => ({ items: [] })),
      fetchExpertiseMap(currentUser.id, projectId, expertiseMapView).catch(() => null),
    ]);
    setAuditEvents(audit.events);
    setTerms(termsResult.entries);
    setApprovals(approvalsResult.items);
    setWorkspace((current) =>
      current
        ? {
            ...current,
            terms: termsResult.entries,
            approvals: approvalsResult.items,
          }
        : current,
    );
    setExpertiseMap(mapResult);
  }

  function handleMapViewChange(nextView: ExpertiseMap["view"]) {
    setExpertiseMapView(nextView);
  }

  async function refreshWorkspace() {
    if (!currentUser) return;
    const data = await fetchUserWorkspace(currentUser.id, projectId);
    setWorkspace(data);
    setTerms(data.terms);
    setApprovals(data.approvals);
    await refreshSidebarData();
  }

  async function handleSelectUser(user: User) {
    setLoading(true);
    setError(null);
    setCurrentUser(user);
    setWorkspace(null);
    setPlazaProjects([]);
    setSelected(null);
    setRecommendation(null);
    setAuditEvents([]);
    setAssistantQuery("");
    setAssistantResult(null);
    setProjectId("");
    setScreen("plaza");
    try {
      const [plaza, userProjects] = await Promise.all([
        fetchPlaza(user.id),
        fetchUserProjects(user.id),
      ]);
      setPlazaProjects(plaza.projects);
      setProjects(userProjects.projects);
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "用户项目加载失败");
      setLoading(false);
    }
  }

  function handleLogout() {
    setCurrentUser(null);
    setWorkspace(null);
    setPlazaProjects([]);
    setProjects([]);
    setProjectId("");
    setScreen("plaza");
    setSelected(null);
    setRecommendation(null);
    setAuditEvents([]);
    setActionStatus("");
    setTerms([]);
    setApprovals([]);
    setExpertiseMap(null);
    setExpertiseMapView("person");
    setAgentIntakeResult(null);
    setAssistantQuery("");
    setAssistantResult(null);
  }

  function handleNavigate(sectionId: NavigationSectionId) {
    setActiveSection(sectionId);
    setSelected(null);
  }

  function findProjectActorByUserId(userId: string | null | undefined): Actor | undefined {
    if (!userId || !workspace) return undefined;
    return workspace.actors.find((actor) => actor.actor_type === "human" && actor.id === userId);
  }

  const selectedTitle = useMemo(() => {
    if (!selected) return "未选择对象";
    if ("title" in selected.item) return selected.item.title;
    if ("canonical_term" in selected.item) return selected.item.canonical_term;
    if ("name" in selected.item) return selected.item.name;
    return "对象详情";
  }, [selected]);

  async function handleRecommend(task: Task) {
    if (!workspace) return;
    setSelected({ kind: "task", item: task });
    setRecommendation(null);
    setRecommendationTaskId(task.id);
    setRecommendingTaskId(task.id);
    const result = await fetchRecommendations(workspace.project.id, task.id);
    setRecommendation(result);
    setRecommendingTaskId(null);
  }

  async function handleSaveConfig() {
    if (!workspace) return;
    const result = await saveLLMConfig(workspace.project.id, llmConfig);
    setConfigStatus(`已保存，密钥显示为 ${result.api_key_masked}`);
  }

  async function handleCreateMemory() {
    if (!workspace) return;
    const created = await createMemory(workspace.project.id, memoryForm);
    setActionStatus(`已创建结构化记忆“${created.title}”，状态为待审阅。`);
    setMemoryForm(defaultMemoryForm);
    setMemoryFormOpen(false);
    await refreshWorkspace();
  }

  async function handleApproveMemory(memory: MemoryItem) {
    if (!currentUser || !workspace) return;
    const approval = approvals.find((item) => item.object_type === "memory" && item.object_id === memory.id && item.status === "pending");
    if (!approval) {
      setActionStatus("当前记忆没有可用的组长审批项。");
      return;
    }
    await handleApproveItem(approval, "approved");
    await refreshWorkspace();
  }

  async function handleGenerateHandover() {
    if (!workspace) return;
    const bundle = await generateHandover(workspace.project.id);
    setHandover(bundle);
    setActionStatus("已生成交接包草稿，等待负责人审阅。");
    await refreshWorkspace();
  }

  async function handleDegradeMode() {
    if (!workspace) return;
    const degraded = workspace.system_state.mode !== "manual_collaboration";
    await setSystemMode(workspace.project.id, {
      mode: degraded ? "manual_collaboration" : "normal",
      label: degraded ? "人工协作模式" : "正常模式",
      message: degraded ? "模型服务不可用，自动摘要和结构化提取已暂停。" : "TMS 推荐、结构化记忆和人工审阅流程可用。",
      llm_available: !degraded,
      vector_search_available: !degraded,
      async_queue_available: true,
      database_writable: true,
    });
    await refreshWorkspace();
  }

  async function handleAdvanceWorkflow(workflow: TMSWorkflow) {
    if (!workspace || !currentUser) return;
    const updated = await advanceWorkflow(currentUser.id, workspace.project.id, workflow.id, {
      note: `${currentUser.name} 完成组长最终确认`,
    });
    setSelected({ kind: "workflow", item: updated });
    setActionStatus(updated.state_message || `已推进闭环“${updated.title}”。`);
    await refreshWorkspace();
  }

  async function handleCreateTerm() {
    if (!currentUser || !workspace) return;
    const payload = {
      ...termForm,
      aliases: splitChineseList(termForm.aliases.join("，")),
      related_terms: splitChineseList(termForm.related_terms.join("，")),
      do_not_confuse_with: splitChineseList(termForm.do_not_confuse_with.join("，")),
      owner: termForm.owner || currentUser.name,
    };
    const created = await createTerm(currentUser.id, workspace.project.id, payload);
    setActionStatus(`术语“${created.canonical_term}”已提交待审阅。`);
    setTermForm(defaultTermForm);
    setTermFormOpen(false);
    await refreshWorkspace();
  }

  async function handleApproveItem(item: ApprovalItem, decision: "approved" | "rejected") {
    if (!currentUser || !workspace) return;
    const updated = await decideApproval(currentUser.id, workspace.project.id, item.id, {
      decision,
      comment: decision === "approved" ? "界面批准" : "界面驳回",
    });
    setActionStatus(`审批项“${updated.title}”已${decision === "approved" ? "批准" : "驳回"}。`);
    await refreshWorkspace();
  }

  async function handleAgentIntake(forceExecute = false) {
    if (!currentUser || !workspace) return;
    setIsAgentIntakeBusy(true);
    try {
      const result = await runAgentIntake(currentUser.id, workspace.project.id, {
        ...agentIntakeForm,
        project_id: workspace.project.id,
        force_execute: forceExecute,
      });
      setAgentIntakeResult(result);
      setAgentIntakeOpen(false);
      if (result.readiness.force_executed) {
        setActionStatus(`已强制执行 ${result.structured_candidate.object_type} 结构化草稿，并写入审核层。`);
      } else if (!result.readiness.ready) {
        setActionStatus(result.readiness.risk_summary || result.readiness.message);
      } else {
        setActionStatus(`已生成 ${result.structured_candidate.object_type} 的结构化草稿。`);
      }
      if (result.saved_review_memory_id) {
        await refreshWorkspace();
      } else {
        await refreshSidebarData();
      }
    } finally {
      setIsAgentIntakeBusy(false);
    }
  }

  async function handleSearch(value: string) {
    setSearchTerm(value);
  }

  async function handleAssistantQuery() {
    if (!currentUser || !workspace || !assistantQuery.trim()) return;
    setIsAssistantBusy(true);
    try {
      const result = await queryProjectAssistant(currentUser.id, workspace.project.id, assistantQuery.trim());
      setAssistantResult(result);
    } finally {
      setIsAssistantBusy(false);
    }
  }

  async function handleCreateProject() {
    if (!currentUser) return;
    const created = await createProject(currentUser.id, projectCreateForm);
    setActionStatus(`项目广场已新增“${created.name}”。`);
    setProjectCreateForm(defaultProjectCreateForm);
    setProjectCreateOpen(false);
    await refreshPlaza();
  }

  async function handleCreateProjectSourceText() {
    if (!currentUser || !workspace) return;
    if (!projectSourceTextForm.content.trim()) {
      setActionStatus("请先粘贴项目资料内容。");
      return;
    }
    const created = await createProjectSourceText(currentUser.id, workspace.project.id, projectSourceTextForm);
    setActionStatus(`项目资料“${created.title}”已进入审核层。`);
    setProjectSourceTextForm(defaultProjectSourceTextForm);
    setProjectSourceOpen(false);
    await refreshWorkspace();
  }

  async function handleUploadProjectSourceFile() {
    if (!currentUser || !workspace || !projectSourceFile) return;
    const isMarkdown = projectSourceFile.name.toLowerCase().endsWith(".md");
    const created = isMarkdown
      ? await uploadProjectSourceMarkdown(currentUser.id, workspace.project.id, projectSourceFile)
      : await uploadProjectSourcePdf(currentUser.id, workspace.project.id, projectSourceFile);
    setActionStatus(`${isMarkdown ? "Markdown 文档" : "PDF 文档"}“${created.file_name ?? created.title}”已进入审核层。`);
    setProjectSourceFile(null);
    setProjectSourceOpen(false);
    await refreshWorkspace();
  }

  async function handleSubmitCapability() {
    if (!currentUser || !workspace) return;
    if (!capabilityForm.rawText.trim()) {
      setActionStatus("请先填写项目内能力描述。");
      return;
    }
    const created = await submitCapability(currentUser.id, workspace.project.id, capabilityForm.rawText, capabilityProofFile);
    setActionStatus(`项目内能力画像已进入审核层，初始置信度 ${created.expert_profile.initial_confidence.toFixed(2)}。`);
    setCapabilityForm(defaultCapabilityForm);
    setCapabilityProofFile(null);
    setCapabilityOpen(false);
    await refreshWorkspace();
  }

  async function handleRunPlanningAgent(forceGenerate = false) {
    if (!currentUser || !workspace) return;
    setIsPlanningBusy(true);
    setPlanningBusyLabel(forceGenerate ? "正在强行生成高风险草稿，请稍候。" : "正在分析共享层并生成计划，请稍候。");
    try {
      const result = await runPlanningAgent(currentUser.id, workspace.project.id, { force_generate: forceGenerate });
      setPlanningResult(result);
      setPlanEditText(JSON.stringify(result.plan.structured_plan, null, 2));
      await refreshWorkspace();
      if (result.plan.generation_mode === "forced_risky") {
        setActionStatus("已生成一版高风险草稿，请先补充材料后再转为正式计划。");
        return;
      }
      if (result.plan.planning_readiness && !result.plan.planning_readiness.ready) {
        setActionStatus(result.plan.planning_readiness.risk_summary || result.plan.planning_readiness.message);
        return;
      }
      setActionStatus(`规划智能体已完成，生成计划草稿 v${result.plan.version}。`);
    } finally {
      setIsPlanningBusy(false);
      setPlanningBusyLabel("");
    }
  }

  function handleSupplementMaterials() {
    const missing = planningResult?.plan.planning_readiness?.missing_items ?? [];
    if (missing.includes("approved_project_capabilities")) {
      setCapabilityOpen(true);
      return;
    }
    setProjectSourceOpen(true);
  }

  async function handleRevisePlan() {
    if (!currentUser || !workspace || !planningResult) return;
    const revisedPlan = await revisePlan(currentUser.id, workspace.project.id, planningResult.plan.id, {
      leader_feedback: planEditFeedback,
      structured_plan: JSON.parse(planEditText),
    });
    setPlanningResult({
      ...planningResult,
      plan: revisedPlan,
    });
    setPlanEditOpen(false);
    setActionStatus("组长已修改计划草稿，等待再次确认。");
  }

  async function handleRegeneratePlan() {
    if (!currentUser || !workspace || !planningResult) return;
    const regenerated = await regeneratePlan(currentUser.id, workspace.project.id, planningResult.plan.id);
    setPlanningResult(regenerated);
    setPlanEditText(JSON.stringify(regenerated.plan.structured_plan, null, 2));
    await refreshWorkspace();
    setActionStatus(`计划草稿已退回重做，生成新草稿 v${regenerated.plan.version}。`);
  }

  async function handleApprovePlan() {
    if (!currentUser || !workspace || !planningResult) return;
    const approved = await approvePlan(currentUser.id, workspace.project.id, planningResult.plan.id, "计划通过，开始发放任务");
    setTaskDraftResult({ planId: approved.plan.id, tasks: approved.tasks });
    setPlanningResult({
      ...planningResult,
      plan: approved.plan,
      plan_memory: approved.plan_memory,
    });
    setActionStatus(`计划草稿 v${approved.plan.version} 已批准，正式计划已进入共享层，任务闭环已生成。`);
    await refreshWorkspace();
  }

  async function handleSubmitTaskResult() {
    if (!currentUser || !workspace || !activeTask) return;
    const result = await submitTaskResult(currentUser.id, workspace.project.id, activeTask.id, taskSubmitForm, taskResultFile);
    setActionStatus(`任务“${result.task?.title ?? activeTask.title}”已提交，等待下游专家开始验收。`);
    setTaskSubmitForm(defaultTaskSubmitForm);
    setTaskResultFile(null);
    setTaskSubmitOpen(false);
    setActiveTask(null);
    await refreshWorkspace();
  }

  async function handleStartAcceptance(task: Task) {
    if (!currentUser || !workspace) return;
    const result = await startAcceptance(currentUser.id, workspace.project.id, task.id);
    setActionStatus(`已开始验收前序任务“${result.previous_task?.title ?? ""}”。`);
    await refreshWorkspace();
  }

  async function handleAcceptanceDecision(task: Task, decision: "accepted" | "rejected") {
    if (!currentUser || !workspace) return;
    const payload = {
      ...acceptanceDecisionForm,
      decision,
      comment: acceptanceDecisionForm.comment || (decision === "accepted" ? "可继续下一步" : "需要回流补充"),
    };
    const result: AcceptanceActionResult = await decideAcceptance(currentUser.id, workspace.project.id, task.id, payload);
    setActionStatus(
      decision === "accepted"
        ? `下游验收已通过，等待组长最终确认后才会正式推进到“${result.current_task?.title ?? task.title}”。`
        : `前序任务已驳回，需回流重做。`,
    );
    setAcceptanceDecisionForm(defaultAcceptanceDecisionForm);
    setAcceptanceOpen(false);
    setActiveTask(null);
    await refreshWorkspace();
  }

  async function handleJoinProject(project: PlazaProjectCard) {
    if (!currentUser) return;
    const created = await createJoinRequest(currentUser.id, project.id, `申请加入项目：${project.name}`);
    setActionStatus(`已向项目“${project.name}”发起申请。`);
    setSelected(null);
    await refreshPlaza();
    return created;
  }

  async function handleApproveJoinRequest(projectIdValue: string, requestId: string) {
    if (!currentUser) return;
    const approved = await approveJoinRequest(currentUser.id, projectIdValue, requestId);
    setActionStatus(`已同意用户 ${approved.applicant_user_id} 加入项目。`);
    await refreshPlaza();
  }

  async function handleRejectJoinRequest(projectIdValue: string, requestId: string) {
    if (!currentUser) return;
    const rejected = await rejectJoinRequest(currentUser.id, projectIdValue, requestId, "当前阶段暂不增加成员。");
    setActionStatus(`已拒绝用户 ${rejected.applicant_user_id} 的加入申请。`);
    await refreshPlaza();
  }

  async function handleOpenProject(project: Project | PlazaProjectCard) {
    if (!currentUser) return;
    setLoading(true);
    setError(null);
    setExpertiseMapView("person");
    setPlanningResult(null);
    setAgentIntakeResult(null);
    try {
      const userProjects = await fetchUserProjects(currentUser.id);
      setProjects(userProjects.projects);
      setProjectId(project.id);
      setScreen("workspace");
    } catch (err) {
      setError(err instanceof Error ? err.message : "项目打开失败");
      setLoading(false);
    }
  }

  function handleBackToPlaza() {
    setWorkspace(null);
    setProjectId("");
    setExpertiseMapView("person");
    setSelected(null);
    setRecommendation(null);
    setRecommendationTaskId(null);
    setPlanningResult(null);
    setAgentIntakeResult(null);
    setScreen("plaza");
    void refreshPlaza();
  }

  if (loading) {
    return (
      <main className="center-screen">
        <Loader2 className="spin" size={28} />
        <span>{currentUser ? "正在加载研究工作台" : "正在加载用户列表"}</span>
      </main>
    );
  }

  if (!currentUser) {
    return <LoginScreen users={users} error={error} onSelectUser={(user) => void handleSelectUser(user)} />;
  }

  if (screen === "plaza") {
    return (
      <PlazaScreen
        actionStatus={actionStatus}
        currentUser={currentUser}
        onApproveJoinRequest={(projectIdValue, requestId) => void handleApproveJoinRequest(projectIdValue, requestId)}
        onCreateProject={() => setProjectCreateOpen(true)}
        onEnterProject={(project) => void handleOpenProject(project)}
        onJoinProject={(project) => void handleJoinProject(project)}
        onLogout={handleLogout}
        onRejectJoinRequest={(projectIdValue, requestId) => void handleRejectJoinRequest(projectIdValue, requestId)}
        projects={plazaProjects}
      >
        {projectCreateOpen && (
          <Backdrop onClose={() => setProjectCreateOpen(false)} title="新建项目">
            <LabeledInput label="项目名称" value={projectCreateForm.name} onChange={(value) => setProjectCreateForm({ ...projectCreateForm, name: value })} />
            <LabeledTextarea label="内容" value={projectCreateForm.content} onChange={(value) => setProjectCreateForm({ ...projectCreateForm, content: value })} />
            <button className="primary-button" onClick={() => void handleCreateProject()}>
              <FilePlus2 size={17} />
              新建项目
            </button>
          </Backdrop>
        )}
      </PlazaScreen>
    );
  }

  if (error || !workspace) {
    return (
      <main className="center-screen danger">
        <AlertTriangle size={28} />
        <span>加载失败：{error ?? "未知错误"}</span>
      </main>
    );
  }

  const activeUser = currentUser;
  const activeWorkspace = workspace;
  const hasProjectOwnerAccess = activeWorkspace.is_project_leader ?? activeUser.id === activeWorkspace.project.owner_user_id;
  const normalizedSearch = searchTerm.trim().toLowerCase();
  const filteredTasks = activeWorkspace.tasks.filter((task) => matchesSearch([task.title, task.description, task.task_type, ...task.tags], normalizedSearch));
  const filteredMemories = activeWorkspace.memories.filter((memory) =>
    matchesSearch([memory.title, memory.summary, memory.memory_type, memory.source, ...memory.tags], normalizedSearch),
  );
  const filteredDecisions = activeWorkspace.decisions.filter((decision) =>
    matchesSearch([decision.title, decision.decision_body, decision.rationale], normalizedSearch),
  );
  const filteredActors = activeWorkspace.actors.filter((actor) =>
    matchesSearch(
      [
        actor.name,
        actor.role,
        actor.actor_type === "ai" ? "AI 协作代理" : "团队成员",
        actor.contribution_summary ?? "",
        ...actor.expertise_claims.flatMap((claim) => [claim.domain, claim.method, claim.tool]),
      ],
      normalizedSearch,
    ),
  );
  const filteredTerms = terms.filter((term) =>
    matchesSearch([term.canonical_term, term.definition, term.domain_scope, ...term.aliases, ...term.related_terms], normalizedSearch),
  );
  const pendingApprovals = approvals.filter((item) => item.status === "pending");
  const pendingApprovalMemoryIds = new Set(pendingApprovals.filter((item) => item.object_type === "memory").map((item) => item.object_id));
  const memoryHasPendingApproval = (memory: MemoryItem) => pendingApprovalMemoryIds.has(memory.id);
  const searchSummary =
    normalizedSearch.length > 0
      ? `当前筛选结果：任务 ${filteredTasks.length} / 记忆 ${filteredMemories.length} / 决策 ${filteredDecisions.length} / 成员 ${filteredActors.length} / 术语 ${filteredTerms.length}`
      : "";
  const currentSectionMeta = workspaceSectionMeta[activeSection];

  function renderWorkspaceContent() {
    switch (activeSection) {
      case "overview":
        const assignedTasks = activeWorkspace.tasks.filter((task) => task.status === "assigned");
        const submittedTasks = activeWorkspace.tasks.filter((task) => task.status === "submitted" || task.status === "awaiting_acceptance");
        const completedTasks = activeWorkspace.tasks.filter((task) => task.status === "completed");
        const approvalRiskItems = pendingApprovals.slice(0, 4);
        return (
          <section className="workspace-view">
            <section className="action-strip dashboard-command-deck">
              <div className="action-strip__meta">
                <span className="eyebrow">快捷操作</span>
                <h3>项目控制台</h3>
                <p>把规划、资料、能力、记忆与交接收束在一个统一操作层，像后台工作台一样推进项目。</p>
              </div>
              <div className="action-strip__grid">
                {hasProjectOwnerAccess && (
                  <button className="command-tile command-tile--primary" onClick={() => void handleRunPlanningAgent()} disabled={isPlanningBusy}>
                    <span className="command-tile__icon">
                      <Sparkles size={18} />
                    </span>
                    <span className="command-tile__copy">
                      <strong>运行智能规划</strong>
                      <small>{isPlanningBusy ? "大模型正在生成计划" : "生成线性计划与任务链"}</small>
                    </span>
                  </button>
                )}
                <button className="command-tile command-tile--primary" onClick={() => setProjectSourceOpen(true)}>
                  <span className="command-tile__icon">
                    <ClipboardList size={18} />
                  </span>
                  <span className="command-tile__copy">
                    <strong>上传项目资料</strong>
                    <small>补齐项目背景、约束与交付输入</small>
                  </span>
                </button>
                <button className="command-tile command-tile--primary" onClick={() => setCapabilityOpen(true)}>
                  <span className="command-tile__icon">
                    <Network size={18} />
                  </span>
                  <span className="command-tile__copy">
                    <strong>提交项目内能力</strong>
                    <small>沉淀角色专长、边界与审阅能力</small>
                  </span>
                </button>
                <button className="command-tile command-tile--primary" onClick={() => setMemoryFormOpen(true)}>
                  <span className="command-tile__icon">
                    <FilePlus2 size={18} />
                  </span>
                  <span className="command-tile__copy">
                    <strong>新建结构化记忆</strong>
                    <small>把项目事实转成正式共享记忆</small>
                  </span>
                </button>
                <button className="command-tile command-tile--secondary" onClick={() => setTermFormOpen(true)}>
                  <span className="command-tile__icon">
                    <ClipboardCheck size={18} />
                  </span>
                  <span className="command-tile__copy">
                    <strong>新建术语条目</strong>
                    <small>统一概念、别名与项目术语边界</small>
                  </span>
                </button>
                <button className="command-tile command-tile--secondary" onClick={() => setAgentIntakeOpen(true)} disabled={isAgentIntakeBusy}>
                  <span className="command-tile__icon">
                    <Sparkles size={18} />
                  </span>
                  <span className="command-tile__copy">
                    <strong>智能录入</strong>
                    <small>{isAgentIntakeBusy ? "大模型正在分析资料" : "把自然语言转成结构化对象"}</small>
                  </span>
                </button>
                <button className="command-tile command-tile--secondary" onClick={() => void handleGenerateHandover()}>
                  <span className="command-tile__icon">
                    <ClipboardList size={18} />
                  </span>
                  <span className="command-tile__copy">
                    <strong>生成交接包</strong>
                    <small>汇总关键进展、风险与下一步门控</small>
                  </span>
                </button>
              </div>
            </section>

            {recommendation && (
              <RecommendationPanel
                result={recommendation}
                taskTitle={activeWorkspace.tasks.find((task) => task.id === recommendationTaskId)?.title ?? "当前任务"}
              />
            )}

            {planningResult && (
              <PlanningPanel
                result={planningResult}
                canApprove={
                  hasProjectOwnerAccess &&
                  planningResult.plan.plan_status === "draft" &&
                  !(planningResult.plan.planning_readiness && !planningResult.plan.planning_readiness.ready) &&
                  !planningResult.plan.is_stale &&
                  planningResult.plan.generation_mode !== "forced_risky"
                }
                canForceGenerate={hasProjectOwnerAccess && !!planningResult.plan.planning_readiness?.force_generate_allowed}
                isWorking={isPlanningBusy}
                workingLabel={planningBusyLabel || "大模型正在思考，请稍候。"}
                llmDiagnostics={activeWorkspace.llm_diagnostics}
                onApprove={() => void handleApprovePlan()}
                onForceGenerate={() => void handleRunPlanningAgent(true)}
                onSupplement={handleSupplementMaterials}
                onRevise={() => setPlanEditOpen(true)}
                onRegenerate={() => void handleRegeneratePlan()}
              />
            )}

            {agentIntakeResult && (
              <AgentIntakePanel
                result={agentIntakeResult}
                onSupplement={() => setAgentIntakeOpen(true)}
                onForceExecute={() => void handleAgentIntake(true)}
              />
            )}

            {handover && <HandoverPanel bundle={handover} />}

            <section className="workspace-highlight-grid">
              <div className="dashboard-kpi-strip">
                <div className="dashboard-kpi-card dashboard-kpi-card--violet">
                  <span>结构化记忆</span>
                  <strong>{activeWorkspace.memories.length}</strong>
                  <small>当前共享、审核与用户层的记忆总量</small>
                </div>
                <div className="dashboard-kpi-card dashboard-kpi-card--teal">
                  <span>术语条目</span>
                  <strong>{terms.length}</strong>
                  <small>正在统一的概念、别名与术语边界</small>
                </div>
                <div className="dashboard-kpi-card dashboard-kpi-card--blue">
                  <span>审批队列</span>
                  <strong>{pendingApprovals.length}</strong>
                  <small>等待组长治理确认的正式对象</small>
                </div>
                <div className="dashboard-kpi-card dashboard-kpi-card--mint">
                  <span>专家画像</span>
                  <strong>{activeWorkspace.expert_profiles.length}</strong>
                  <small>项目内已生成的能力画像与关系节点</small>
                </div>
              </div>

              <div className="dashboard-board-grid">
                <div className="dashboard-board-grid__main">
                  <div className="panel-card overview-funnel-card">
                    <div className="panel-head">
                      <strong>任务推进漏斗</strong>
                      <span>{activeWorkspace.tasks.length} 项任务</span>
                    </div>
                    <div className="funnel-stage-list">
                      <div className="funnel-stage is-wide">
                        <span>待处理任务</span>
                        <strong>{assignedTasks.length}</strong>
                        <small>当前最需要推进的执行事项</small>
                      </div>
                      <div className="funnel-stage is-medium">
                        <span>待验收与已提交</span>
                        <strong>{submittedTasks.length}</strong>
                        <small>等待下游或组长确认</small>
                      </div>
                      <div className="funnel-stage is-narrow">
                        <span>已完成任务</span>
                        <strong>{completedTasks.length}</strong>
                        <small>已走完当前任务链</small>
                      </div>
                      <div className="funnel-stage is-accent">
                        <span>进行中闭环</span>
                        <strong>{activeWorkspace.workflows.length}</strong>
                        <small>流程、任务链和审批会在这里汇总</small>
                      </div>
                    </div>
                  </div>

                  <div className="panel-card">
                    <div className="panel-head">
                      <strong>系统资产概览</strong>
                      <span>共享层摘要</span>
                    </div>
                    <div className="summary-metrics">
                      <div className="metric-card">
                        <span>结构化记忆</span>
                        <strong>{activeWorkspace.memories.length}</strong>
                      </div>
                      <div className="metric-card">
                        <span>术语条目</span>
                        <strong>{terms.length}</strong>
                      </div>
                      <div className="metric-card">
                        <span>审批队列</span>
                        <strong>{pendingApprovals.length}</strong>
                      </div>
                      <div className="metric-card">
                        <span>专家画像</span>
                        <strong>{activeWorkspace.expert_profiles.length}</strong>
                      </div>
                    </div>
                  </div>

                  <section className="panel-card audit-card">
                    <div className="panel-head">
                      <strong>最近审计日志</strong>
                      <span>关键动作留痕</span>
                    </div>
                    <div className="audit-list">
                      {auditEvents.slice(0, 6).map((event) => (
                        <div className="audit-row" key={event.id}>
                          <strong>{event.action}</strong>
                          <span>{event.message}</span>
                        </div>
                      ))}
                      {auditEvents.length === 0 && <EmptyState label="暂无审计事件" />}
                    </div>
                  </section>
                </div>

                <aside className="insight-rail">
                  <div className="panel-card assistant-summary-card">
                    <div className="panel-head">
                      <strong>助手摘要</strong>
                      <span>协作入口</span>
                    </div>
                    <div className="assistant-shortcut-row">
                      <div className="compact-row">
                        <strong>最近一次提问</strong>
                        <span>{assistantQuery.trim() ? "已有输入" : "尚未输入"}</span>
                        <small>{assistantQuery.trim() || "你可以直接从右侧或顶部提问项目助手。"}</small>
                      </div>
                      <div className="compact-row">
                        <strong>最近一次回答</strong>
                        <span>{assistantResult ? "已返回结果" : "等待提问"}</span>
                        <small>{assistantResult?.answer ?? "系统会优先基于共享层给出中文回答。"}</small>
                      </div>
                    </div>
                  </div>

                  <div className="panel-card">
                    <div className="panel-head">
                      <strong>高风险与提醒</strong>
                      <span>优先关注</span>
                    </div>
                    <div className="compact-list">
                      {!activeWorkspace.system_state.vector_search_available && (
                        <div className="compact-row">
                          <strong>语义检索暂不可用</strong>
                          <span>系统已降级</span>
                          <small>当前仅支持页面内搜索与人工筛选</small>
                        </div>
                      )}
                      {approvalRiskItems.map((item) => (
                        <button className="compact-row" key={item.id} onClick={() => setSelected({ kind: "approval", item })} type="button">
                          <strong>{item.title}</strong>
                          <span>{item.status}</span>
                          <small>{item.reason}</small>
                        </button>
                      ))}
                      {pendingApprovals.length === 0 && activeWorkspace.system_state.vector_search_available && (
                        <EmptyState label="当前没有高优先级风险提醒" />
                      )}
                    </div>
                  </div>
                </aside>
              </div>
            </section>
          </section>
        );
      case "tasks":
        const assignedTaskCards = filteredTasks.filter((task) => task.status === "assigned");
        const submittedTaskCards = filteredTasks.filter((task) => task.status === "submitted" || task.status === "awaiting_acceptance");
        const completedTaskCards = filteredTasks.filter((task) => task.status === "completed");
        const activeWorkflow = activeWorkspace.workflows.find((workflow) => workflow.loop_type === "任务执行闭环" && workflow.current_task_id);
        const activeWorkflowTask = activeWorkspace.tasks.find((task) => task.id === activeWorkflow?.current_task_id);
        return (
          <section className="workspace-view">
            <section className="band">
              <div className="band-title">
                <h3>闭环流程概览</h3>
                <span>先看流程推进，再进入具体任务卡片</span>
              </div>
              {activeWorkflow && activeWorkflowTask && (
                <div className="compact-row workflow-explainer">
                  <strong>当前推进提示</strong>
                  <span>{activeWorkflow.state_message}</span>
                  <small>
                    当前任务：{activeWorkflowTask.title} / 负责人 {activeWorkflowTask.owner_id ?? "待分派"} / 验收人 {activeWorkflowTask.reviewer_user_id ?? "待分派"}
                  </small>
                </div>
              )}
              <div className="card-grid two">
                {activeWorkspace.workflows.map((workflow) => (
                  <WorkflowCard
                    key={workflow.id}
                    workflow={workflow}
                    currentUserId={activeUser.id}
                    onSelect={() => setSelected({ kind: "workflow", item: workflow })}
                    onAdvance={() => void handleAdvanceWorkflow(workflow)}
                  />
                ))}
                {activeWorkspace.workflows.length === 0 && <EmptyState label="暂无闭环流程" />}
              </div>
            </section>

            <section className="band workspace-collapsible">
              <div className="band-title">
                <h3>任务分组面板</h3>
                <span>按当前最重要的处理阶段分区，避免长列表堆叠</span>
              </div>
              <div className="task-stage-grid">
                <section className="panel-card">
                  <div className="panel-head">
                    <strong>待处理任务</strong>
                    <span>{assignedTaskCards.length} 项</span>
                  </div>
                  <div className="card-grid">
                    {assignedTaskCards.slice(0, 4).map((task) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        owner={findProjectActorByUserId(task.owner_id)}
                        predecessorTask={task.predecessor_task_id ? activeWorkspace.tasks.find((item) => item.id === task.predecessor_task_id) : undefined}
                        isTerminalTask={!activeWorkspace.tasks.some((item) => item.predecessor_task_id === task.id)}
                        currentUserId={activeUser.id}
                        recommendation={recommendationTaskId === task.id ? recommendation : null}
                        loading={recommendingTaskId === task.id}
                        onSelect={() => setSelected({ kind: "task", item: task })}
                        onRecommend={() => void handleRecommend(task)}
                        onOpenSubmit={() => {
                          setActiveTask(task);
                          setTaskSubmitOpen(true);
                        }}
                        onStartAcceptance={() => void handleStartAcceptance(task)}
                        onOpenAcceptanceDecision={(decision) => {
                          setActiveTask(task);
                          setAcceptanceDecisionForm({ decision, comment: "" });
                          setAcceptanceOpen(true);
                        }}
                      />
                    ))}
                    {assignedTaskCards.length === 0 && <EmptyState label="当前没有待处理任务" />}
                  </div>
                </section>

                <section className="panel-card">
                  <div className="panel-head">
                    <strong>待验收与已提交</strong>
                    <span>{submittedTaskCards.length} 项</span>
                  </div>
                  <div className="card-grid">
                    {submittedTaskCards.slice(0, 4).map((task) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        owner={findProjectActorByUserId(task.owner_id)}
                        predecessorTask={task.predecessor_task_id ? activeWorkspace.tasks.find((item) => item.id === task.predecessor_task_id) : undefined}
                        isTerminalTask={!activeWorkspace.tasks.some((item) => item.predecessor_task_id === task.id)}
                        currentUserId={activeUser.id}
                        recommendation={recommendationTaskId === task.id ? recommendation : null}
                        loading={recommendingTaskId === task.id}
                        onSelect={() => setSelected({ kind: "task", item: task })}
                        onRecommend={() => void handleRecommend(task)}
                        onOpenSubmit={() => {
                          setActiveTask(task);
                          setTaskSubmitOpen(true);
                        }}
                        onStartAcceptance={() => void handleStartAcceptance(task)}
                        onOpenAcceptanceDecision={(decision) => {
                          setActiveTask(task);
                          setAcceptanceDecisionForm({ decision, comment: "" });
                          setAcceptanceOpen(true);
                        }}
                      />
                    ))}
                    {submittedTaskCards.length === 0 && <EmptyState label="当前没有待验收任务" />}
                  </div>
                </section>

                <section className="panel-card">
                  <div className="panel-head">
                    <strong>已完成归档</strong>
                    <span>{completedTaskCards.length} 项</span>
                  </div>
                  <div className="card-grid">
                    {completedTaskCards.slice(0, 4).map((task) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        owner={findProjectActorByUserId(task.owner_id)}
                        predecessorTask={task.predecessor_task_id ? activeWorkspace.tasks.find((item) => item.id === task.predecessor_task_id) : undefined}
                        isTerminalTask={!activeWorkspace.tasks.some((item) => item.predecessor_task_id === task.id)}
                        currentUserId={activeUser.id}
                        recommendation={recommendationTaskId === task.id ? recommendation : null}
                        loading={recommendingTaskId === task.id}
                        onSelect={() => setSelected({ kind: "task", item: task })}
                        onRecommend={() => void handleRecommend(task)}
                        onOpenSubmit={() => {
                          setActiveTask(task);
                          setTaskSubmitOpen(true);
                        }}
                        onStartAcceptance={() => void handleStartAcceptance(task)}
                        onOpenAcceptanceDecision={(decision) => {
                          setActiveTask(task);
                          setAcceptanceDecisionForm({ decision, comment: "" });
                          setAcceptanceOpen(true);
                        }}
                      />
                    ))}
                    {completedTaskCards.length === 0 && <EmptyState label="当前没有已完成任务" />}
                  </div>
                </section>
              </div>
            </section>
          </section>
        );
      case "memories":
        const draftMemories = filteredMemories
          .filter((memory) => memory.review_status !== "已确认")
          .sort((a, b) => Number(memoryHasPendingApproval(b)) - Number(memoryHasPendingApproval(a)));
        const sharedMemories = filteredMemories
          .filter((memory) => memory.shared)
          .sort((a, b) => Number(b.memory_type === "plan_final") - Number(a.memory_type === "plan_final"));
        return (
          <section className="workspace-view">
            <section className="band workspace-collapsible">
              <div className="band-title">
                <h3>团队记忆</h3>
                <span>按审核状态和共享状态分区，避免一屏拉满所有记忆</span>
              </div>
              <div className="memory-stage-grid">
                <section className="panel-card">
                  <div className="panel-head">
                    <strong>待审阅记忆</strong>
                    <span>{draftMemories.length} 条</span>
                  </div>
                  <div className="card-grid">
                    {draftMemories.map((memory) => (
                      <MemoryCard
                        key={memory.id}
                        canApprove={hasProjectOwnerAccess && memoryHasPendingApproval(memory)}
                        memory={memory}
                        onSelect={() => setSelected({ kind: "memory", item: memory })}
                        onApprove={() => void handleApproveMemory(memory)}
                      />
                    ))}
                    {draftMemories.length === 0 && <EmptyState label="当前没有待审阅记忆" />}
                  </div>
                </section>

                <section className="panel-card">
                  <div className="panel-head">
                    <strong>已共享记忆</strong>
                    <span>{sharedMemories.length} 条</span>
                  </div>
                  <div className="card-grid">
                    {sharedMemories.map((memory) => (
                      <MemoryCard
                        key={memory.id}
                        canApprove={false}
                        memory={memory}
                        onSelect={() => setSelected({ kind: "memory", item: memory })}
                        onApprove={() => void handleApproveMemory(memory)}
                      />
                    ))}
                    {sharedMemories.length === 0 && <EmptyState label="当前没有已共享记忆" />}
                  </div>
                </section>
              </div>
            </section>

            <section className="band">
              <div className="band-title">
                <h3>全部记忆目录</h3>
                <span>保留完整入口，便于筛选和快速定位</span>
              </div>
              <div className="card-grid two">
                {filteredMemories.map((memory) => (
                  <MemoryCard
                    key={memory.id}
                    canApprove={hasProjectOwnerAccess && memoryHasPendingApproval(memory)}
                    memory={memory}
                    onSelect={() => setSelected({ kind: "memory", item: memory })}
                    onApprove={() => void handleApproveMemory(memory)}
                  />
                ))}
                {filteredMemories.length === 0 && <EmptyState label="没有匹配的记忆" />}
              </div>
            </section>
          </section>
        );
      case "experts":
        return (
          <section className="workspace-view">
            <section className="band">
              <div className="band-title">
                <h3>专家网络</h3>
                <span>成员专长、验证状态和信任上下文会一起展示</span>
              </div>
              {expertiseMap && (
                <>
                  <div className="map-summary">
                    <span>视图：{expertiseMapViewLabels[expertiseMap.view]}</span>
                    <span>节点：{expertiseMap.nodes.length}</span>
                    <span>关系：{expertiseMap.edges.length}</span>
                    <span>支持视图：{expertiseMap.supported_views.map((view) => expertiseMapViewLabels[view]).join(" / ")}</span>
                  </div>
                  <div className="graph-toolbar">
                    {expertiseMap.supported_views.map((view) => (
                      <button
                        className={view === expertiseMapView ? "graph-view-button active" : "graph-view-button"}
                        key={view}
                        onClick={() => handleMapViewChange(view)}
                        type="button"
                      >
                        {expertiseMapViewLabels[view]}
                      </button>
                    ))}
                  </div>
                  <ExpertiseMapGraph className="expertise-map-graph" legendClassName="graph-legend" map={expertiseMap} />
                </>
              )}
              <div className="card-grid two">
                {activeWorkspace.expert_profiles.map((profile) => (
                  <article className="object-card" key={profile.id}>
                    <div className="card-head">
                      <span className="type-chip">项目内专家画像</span>
                      <span className="state-chip">{profile.status}</span>
                    </div>
                    <h4>{profile.user_id}</h4>
                    <p>初始置信度：{profile.initial_confidence.toFixed(2)}</p>
                    <div className="meta-line">当前置信度：{profile.current_confidence.toFixed(2)}</div>
                    <div className="meta-line">能力数：{profile.structured_capabilities.length}</div>
                    <div className="tag-row">{profile.structured_capabilities.map((claim) => <span key={`${profile.id}-${claim.domain}`}>{claim.domain}</span>)}</div>
                  </article>
                ))}
                {activeWorkspace.expert_profiles.length === 0 && <EmptyState label="暂未提交项目内能力画像" />}
              </div>
              <div className="relation-panel">
                <strong>关系摘要</strong>
                {activeWorkspace.expert_relations.length === 0 ? (
                  <span className="muted">暂无项目内专家关系</span>
                ) : (
                  activeWorkspace.expert_relations.map((relation) => (
                    <div className="relation-row" key={relation.id}>
                      <span>{relation.from_user_id}</span>
                      <span>{relation.relation_type}</span>
                      <span>{relation.to_user_id}</span>
                      <small>权重 {relation.weight.toFixed(2)}</small>
                    </div>
                  ))
                )}
              </div>
              <div className="card-grid three">
                {filteredActors.map((actor) => (
                  <ActorCard key={actor.id} actor={actor} onSelect={() => setSelected({ kind: "actor", item: actor })} />
                ))}
                {filteredActors.length === 0 && <EmptyState label="没有匹配的成员" />}
              </div>
            </section>
          </section>
        );
      case "governance":
        const visibleDraftPlans = activeWorkspace.plans
          .filter((plan) => plan.plan_status === "draft" || plan.plan_status === "leader_editing")
          .sort((a, b) => b.version - a.version);
        const governancePlanSummary = visibleDraftPlans.length;
        const activeGovernancePlan = planningResult?.plan.plan_status !== "approved"
          ? planningResult
          : visibleDraftPlans[0]
            ? {
                agent_run: {
                  id: visibleDraftPlans[0].generated_by_agent_run_id,
                  project_id: visibleDraftPlans[0].project_id,
                  triggered_by: activeWorkspace.project.owner_user_id ?? activeUser.id,
                  model_name: activeWorkspace.llm_diagnostics?.effective_config.provider_name ?? "DeepSeek V4 Pro",
                  run_type: "project_bootstrap_or_replan",
                  status: "completed" as const,
                  analysis_output_memory_id: activeWorkspace.memories.find((memory) => memory.title.includes("分析结果草稿"))?.id,
                  plan_output_memory_id: activeWorkspace.memories.find((memory) => memory.memory_type === "plan_draft" && memory.title.includes(`v${visibleDraftPlans[0].version}`))?.id,
                  created_at: visibleDraftPlans[0].created_at,
                },
                analysis_memory:
                  activeWorkspace.memories.find((memory) => memory.title.includes("分析结果草稿")) ??
                  activeWorkspace.memories[0],
                plan_memory:
                  activeWorkspace.memories.find((memory) => memory.memory_type === "plan_draft" && memory.title.includes(`v${visibleDraftPlans[0].version}`)) ??
                  activeWorkspace.memories[0],
                plan: visibleDraftPlans[0],
              }
            : null;
        return (
          <section className="workspace-view">
            <section className="band">
              <div className="band-title">
                <h3>术语与治理</h3>
                <span>把治理信息拆成三个短面板，避免同页过长</span>
              </div>
              <div className="governance-tab-strip">
                <div className="governance-tab-card">
                  <span className="eyebrow">计划治理</span>
                  <strong>{governancePlanSummary > 0 ? "已有计划草稿" : "暂无计划草稿"}</strong>
                  <small>组长可在此查看、修改、批准或退回计划</small>
                </div>
                <div className="governance-tab-card">
                  <span className="eyebrow">术语对齐</span>
                  <strong>{filteredTerms.length} 条术语</strong>
                  <small>统一术语定义、别名和示例用法</small>
                </div>
                <div className="governance-tab-card">
                  <span className="eyebrow">审批队列</span>
                  <strong>{pendingApprovals.length} 项待处理</strong>
                  <small>统一承接记忆、术语和治理审批</small>
                </div>
              </div>

              <div className="card-grid two governance-grid">
                <div className="panel-card">
                  <div className="panel-head">
                    <strong>计划治理</strong>
                    <span>{activeGovernancePlan ? activeGovernancePlan.plan.plan_status : "暂无草稿"}</span>
                  </div>
                  {activeGovernancePlan ? (
                    <div className="compact-list">
                      <button className="compact-row" onClick={() => setSelected({ kind: "memory", item: activeGovernancePlan.plan_memory })} type="button">
                        <strong>{activeGovernancePlan.plan.plan_title}</strong>
                        <span>v{activeGovernancePlan.plan.version}</span>
                        <small>{activeGovernancePlan.plan.plan_summary}</small>
                      </button>
                      {hasProjectOwnerAccess && activeGovernancePlan.plan.plan_status !== "approved" && (
                        <div className="approval-actions">
                          {activeGovernancePlan.plan.generation_mode !== "forced_risky" && (!activeGovernancePlan.plan.planning_readiness || activeGovernancePlan.plan.planning_readiness.ready) && (
                            <button className="mini-approve" onClick={() => { setPlanningResult(activeGovernancePlan); void handleApprovePlan(); }} type="button">
                              批准计划
                            </button>
                          )}
                          <button className="mini-approve" onClick={() => { setPlanningResult(activeGovernancePlan); setPlanEditOpen(true); }} type="button">
                            修改
                          </button>
                          <button className="mini-reject" onClick={() => { setPlanningResult(activeGovernancePlan); void handleRegeneratePlan(); }} type="button">
                            退回重做
                          </button>
                        </div>
                      )}
                    </div>
                  ) : (
                    <EmptyState label="暂无待治理计划草稿" />
                  )}
                </div>

                <div className="panel-card">
                  <div className="panel-head">
                    <strong>术语条目</strong>
                    <span>{activeWorkspace.terms.length} 条</span>
                  </div>
                  <div className="compact-list">
                    {filteredTerms.slice(0, 6).map((term) => (
                      <button className="compact-row" key={term.id} onClick={() => setSelected({ kind: "term", item: term })} type="button">
                        <strong>{term.canonical_term}</strong>
                        <span>{term.review_status}</span>
                        <small>{term.aliases.join(" / ") || "无别名"}</small>
                      </button>
                    ))}
                    {filteredTerms.length === 0 && <EmptyState label="没有匹配的术语" />}
                  </div>
                </div>

                <div className="panel-card">
                  <div className="panel-head">
                    <strong>审批队列</strong>
                    <span>{pendingApprovals.length} 项待处理</span>
                  </div>
                  <div className="compact-list">
                    {hasProjectOwnerAccess &&
                      pendingApprovals.map((item) => (
                        <div className="approval-card" key={item.id}>
                          <button className="compact-row" onClick={() => setSelected({ kind: "approval", item })} type="button">
                            <strong>{item.title}</strong>
                            <span>{item.status}</span>
                            <small>{item.reason}</small>
                          </button>
                          {item.status === "pending" && (
                            <div className="approval-actions">
                              <button className="mini-approve" onClick={() => void handleApproveItem(item, "approved")} type="button">
                                批准
                              </button>
                              <button className="mini-reject" onClick={() => void handleApproveItem(item, "rejected")} type="button">
                                驳回
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                    {!hasProjectOwnerAccess && <EmptyState label="审批队列仅组长可见" />}
                    {hasProjectOwnerAccess && pendingApprovals.length === 0 && <EmptyState label="暂无待处理审批项" />}
                  </div>
                </div>
              </div>
            </section>
          </section>
        );
      case "decisions":
        const handoverBundles = activeWorkspace.handover_bundles;
        return (
          <section className="workspace-view">
            <section className="band workspace-collapsible">
              <div className="band-title">
                <h3>决策与交接</h3>
                <span>将决策与交接拆成双区切换，避免单列过长</span>
              </div>
              <div className="decision-switch-grid">
                <section className="panel-card">
                  <div className="panel-head">
                    <strong>关键决策</strong>
                    <span>{filteredDecisions.length} 条</span>
                  </div>
                  <div className="card-grid">
                    {filteredDecisions.slice(0, 4).map((decision) => (
                      <DecisionCard key={decision.id} decision={decision} onSelect={() => setSelected({ kind: "decision", item: decision })} />
                    ))}
                    {filteredDecisions.length === 0 && <EmptyState label="当前没有决策记录" />}
                  </div>
                </section>

                <section className="panel-card">
                  <div className="panel-head">
                    <strong>交接摘要</strong>
                    <span>{handoverBundles.length} 个</span>
                  </div>
                  <div className="card-grid">
                    {handoverBundles.slice(0, 4).map((bundle) => (
                      <HandoverCard key={bundle.id} bundle={bundle} onSelect={() => setSelected({ kind: "handover", item: bundle })} />
                    ))}
                    {handoverBundles.length === 0 && <EmptyState label="当前没有交接包" />}
                  </div>
                </section>
              </div>
            </section>

            <section className="band">
              <div className="band-title">
                <h3>审计日志</h3>
                <span>关键自动化和审批动作都会留下记录</span>
              </div>
              <div className="audit-list">
                {auditEvents.slice(0, 6).map((event) => (
                  <div className="audit-row" key={event.id}>
                    <strong>{event.action}</strong>
                    <span>{event.message}</span>
                  </div>
                ))}
                {auditEvents.length === 0 && <EmptyState label="暂无审计事件" />}
              </div>
            </section>
          </section>
        );
      default:
        return null;
    }
  }

  const isAnyModelBusy = isPlanningBusy || isAgentIntakeBusy || isAssistantBusy;
  const globalThinkingLabel = isPlanningBusy
    ? planningBusyLabel || "大模型正在生成计划，请稍候。"
    : isAgentIntakeBusy
      ? "大模型正在分析资料，请稍候。"
      : isAssistantBusy
        ? "项目助手正在整理共享层回答，请稍候。"
        : "";

  return (
    <main className="dashboard-shell">
      <section className="dashboard-frame">
        <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Brain size={26} />
          <div>
            <strong>研究协作台</strong>
            <span>用户协作工作台</span>
          </div>
        </div>

        <section className="user-block">
          <span className="eyebrow">当前用户</span>
          <div className="current-user-card">
            <UserRound size={18} />
            <div>
              <strong>{currentUser.name}</strong>
              <span>{currentUser.role}</span>
            </div>
          </div>
          <button className="text-button" onClick={handleLogout}>
            <LogOut size={15} />
            切换用户
          </button>
          <button className="text-button" onClick={handleBackToPlaza}>
            <PanelRightOpen size={15} />
            返回项目广场
          </button>
        </section>

        <section className="project-block">
          <span className="eyebrow">当前项目</span>
          <h1>{activeWorkspace.project.name}</h1>
          <label className="project-switcher">
            切换项目
            <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>
          <p>{activeWorkspace.project.summary}</p>
          <div className="status-pill">{activeWorkspace.project.stage}</div>
        </section>

        <nav className="nav-list" aria-label="项目导航">
          {navigationItems.map((item) => {
            const Icon = item.icon;
            return (
              <button className={activeSection === item.id ? "active" : ""} key={item.id} onClick={() => handleNavigate(item.id)} type="button">
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>

        <section className="side-section">
          <span className="eyebrow">系统状态</span>
          <div className="system-state">
            <CheckCircle2 size={18} />
            <div>
              <strong>{activeWorkspace.system_state.label}</strong>
              <span>{activeWorkspace.system_state.message}</span>
            </div>
          </div>
          {!activeWorkspace.system_state.vector_search_available && (
            <div className="status-warning">当前顶部搜索使用页面内筛选；后端语义检索暂不可用。</div>
          )}
        </section>

        <button className="settings-button" onClick={() => setConfigOpen(true)}>
          <Settings size={18} />
          模型配置
        </button>
        <button className="settings-button" onClick={handleDegradeMode}>
          <ShieldCheck size={18} />
          切换降级模式
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar workspace-stage-header">
          <div>
            <span className="eyebrow">项目工作区</span>
            <h2>{currentSectionMeta.title}</h2>
            <p className="workspace-description">{currentSectionMeta.description}</p>
          </div>
          <div className="workspace-stage-header__tools">
            <label className="search-box" aria-label="搜索任务、记忆、决策、成员">
              <Search size={17} />
              <input value={searchTerm} onChange={(event) => void handleSearch(event.target.value)} placeholder="搜索任务、记忆、决策、成员" />
            </label>
            <div className="topbar-user-card">
              <UserRound size={18} />
              <div>
                <strong>{activeUser.name}</strong>
                <span>{activeUser.role}</span>
              </div>
            </div>
          </div>
        </header>

        <GlobalStatusBanner message={actionStatus} onClose={() => setActionStatus("")} />

        {searchSummary && (
          <section className="notice-strip">
            <Search size={16} />
            <span>{searchSummary}</span>
          </section>
        )}
        <div className="assistant-mobile-shell">
          <ProjectAssistantPanel
            className="assistant-mobile"
            assistantQuery={assistantQuery}
            assistantResult={assistantResult}
            isThinking={isAssistantBusy}
            onAssistantQueryChange={setAssistantQuery}
            onSubmit={() => void handleAssistantQuery()}
          />
        </div>

        <div className="workspace-section-content">{renderWorkspaceContent()}</div>
      </section>

      <aside className="detail-panel detail-rail">
        <div className="assistant-sidebar">
          <ProjectAssistantPanel
            assistantQuery={assistantQuery}
            assistantResult={assistantResult}
            isThinking={isAssistantBusy}
            onAssistantQueryChange={setAssistantQuery}
            onSubmit={() => void handleAssistantQuery()}
          />
        </div>
        <div className="detail-sidebar detail-drawer-shell">
          <span className="eyebrow">对象详情</span>
          <h2>{selectedTitle}</h2>
          <DetailView selected={selected} recommendation={recommendation} expertiseMap={expertiseMap} />
        </div>
      </aside>

      {configOpen && (
        <Backdrop onClose={() => setConfigOpen(false)} title="模型配置">
          <LabeledInput label="提供方名称" value={llmConfig.provider_name} onChange={(value) => setLLMConfig({ ...llmConfig, provider_name: value })} />
          <LabeledInput label="接口地址" value={llmConfig.base_url} onChange={(value) => setLLMConfig({ ...llmConfig, base_url: value })} />
          <LabeledInput label="密钥" type="password" value={llmConfig.api_key} onChange={(value) => setLLMConfig({ ...llmConfig, api_key: value })} />
          <LabeledInput label="默认对话模型" value={llmConfig.chat_model} onChange={(value) => setLLMConfig({ ...llmConfig, chat_model: value })} />
          <LabeledInput label="默认嵌入模型" value={llmConfig.embedding_model} onChange={(value) => setLLMConfig({ ...llmConfig, embedding_model: value })} />
          <div className="form-row">
            <label>
              温度
              <input type="number" step="0.1" min="0" max="2" value={llmConfig.temperature} onChange={(event) => setLLMConfig({ ...llmConfig, temperature: Number(event.target.value) })} />
            </label>
            <label>
              最大输出
              <input type="number" min="1" value={llmConfig.max_tokens} onChange={(event) => setLLMConfig({ ...llmConfig, max_tokens: Number(event.target.value) })} />
            </label>
          </div>
          <button className="primary-button" onClick={() => void handleSaveConfig()}>
            <KeyRound size={17} />
            保存项目配置
          </button>
          <p className="config-status">{configStatus}</p>
        </Backdrop>
      )}

      {projectSourceOpen && (
        <Backdrop onClose={() => setProjectSourceOpen(false)} title="上传项目资料">
          <LabeledInput
            label="资料标题"
            value={projectSourceTextForm.title}
            onChange={(value) => setProjectSourceTextForm({ ...projectSourceTextForm, title: value })}
          />
          <LabeledTextarea
            label="粘贴文字内容"
            value={projectSourceTextForm.content}
            onChange={(value) => setProjectSourceTextForm({ ...projectSourceTextForm, content: value })}
          />
          <button className="primary-button" onClick={() => void handleCreateProjectSourceText()}>
            <FilePlus2 size={17} />
            提交文字资料
          </button>
          <label className="field field-file">
            上传 PDF 文档或 Markdown 文档
            <span className="file-picker-shell">
              <span className="file-picker-button">选择文件</span>
              <span className="file-picker-name">{projectSourceFile?.name ?? "未选择任何文件"}</span>
              <input type="file" accept=".pdf,application/pdf,.md,text/markdown,text/plain" onChange={(event) => setProjectSourceFile(event.target.files?.[0] ?? null)} />
            </span>
          </label>
          <button className="secondary-button" onClick={() => void handleUploadProjectSourceFile()}>
            <ClipboardList size={17} />
            上传文件资料
          </button>
        </Backdrop>
      )}

      {capabilityOpen && (
        <Backdrop onClose={() => setCapabilityOpen(false)} title="提交项目内能力">
          <LabeledTextarea
            label="能力描述"
            value={capabilityForm.rawText}
            onChange={(value) => setCapabilityForm({ rawText: value })}
          />
          <p className="muted">当前支持直接用文本提交项目内能力；如你愿意，也可以附加 PDF 证明材料，但不再是必填项。</p>
          <label className="field field-file">
            可选：上传证明 PDF 文档
            <span className="file-picker-shell">
              <span className="file-picker-button">选择文件</span>
              <span className="file-picker-name">{capabilityProofFile?.name ?? "未选择任何文件"}</span>
              <input type="file" accept=".pdf,application/pdf" onChange={(event) => setCapabilityProofFile(event.target.files?.[0] ?? null)} />
            </span>
          </label>
          <button className="primary-button" onClick={() => void handleSubmitCapability()}>
            <Network size={17} />
            提交项目内能力
          </button>
        </Backdrop>
      )}

      {taskSubmitOpen && activeTask && (
        <Backdrop onClose={() => setTaskSubmitOpen(false)} title="提交任务结果">
          <LabeledTextarea
            label="完成摘要"
            value={taskSubmitForm.summary}
            onChange={(value) => setTaskSubmitForm({ ...taskSubmitForm, summary: value })}
          />
          <LabeledTextarea
            label="交接说明"
            value={taskSubmitForm.handoff_note}
            onChange={(value) => setTaskSubmitForm({ ...taskSubmitForm, handoff_note: value })}
          />
          <label className="field field-file">
            上传结果 PDF 文档
            <span className="file-picker-shell">
              <span className="file-picker-button">选择文件</span>
              <span className="file-picker-name">{taskResultFile?.name ?? "未选择任何文件"}</span>
              <input type="file" accept=".pdf,application/pdf" onChange={(event) => setTaskResultFile(event.target.files?.[0] ?? null)} />
            </span>
          </label>
          <button className="primary-button" onClick={() => void handleSubmitTaskResult()}>
            <CheckCircle2 size={17} />
            我已完成
          </button>
        </Backdrop>
      )}

      {acceptanceOpen && activeTask && (
        <Backdrop onClose={() => setAcceptanceOpen(false)} title="验收决策">
          <label className="field">
            验收结果
            <select
              value={acceptanceDecisionForm.decision}
              onChange={(event) =>
                setAcceptanceDecisionForm({
                  ...acceptanceDecisionForm,
                  decision: event.target.value as "accepted" | "rejected",
                })
              }
            >
              <option value="accepted">验收通过</option>
              <option value="rejected">驳回</option>
            </select>
          </label>
          <LabeledTextarea
            label="说明"
            value={acceptanceDecisionForm.comment}
            onChange={(value) => setAcceptanceDecisionForm({ ...acceptanceDecisionForm, comment: value })}
          />
          <button className="primary-button" onClick={() => void handleAcceptanceDecision(activeTask, acceptanceDecisionForm.decision)}>
            <ClipboardCheck size={17} />
            提交验收结果
          </button>
        </Backdrop>
      )}

      {planEditOpen && planningResult && (
        <Backdrop onClose={() => setPlanEditOpen(false)} title="修改计划">
          <LabeledTextarea label="组长反馈" value={planEditFeedback} onChange={setPlanEditFeedback} />
          <LabeledTextarea label="结构化计划数据" value={planEditText} onChange={setPlanEditText} />
          <button className="primary-button" onClick={() => void handleRevisePlan()}>
            <ClipboardCheck size={17} />
            修改计划
          </button>
        </Backdrop>
      )}

      {memoryFormOpen && (
        <Backdrop onClose={() => setMemoryFormOpen(false)} title="新建结构化记忆">
          <LabeledInput label="记忆类型" value={memoryForm.memory_type} onChange={(value) => setMemoryForm({ ...memoryForm, memory_type: value })} />
          <LabeledInput label="标题" value={memoryForm.title} onChange={(value) => setMemoryForm({ ...memoryForm, title: value })} />
          <LabeledTextarea label="摘要" value={memoryForm.summary} onChange={(value) => setMemoryForm({ ...memoryForm, summary: value })} />
          <LabeledInput label="来源" value={memoryForm.source} onChange={(value) => setMemoryForm({ ...memoryForm, source: value })} />
          <LabeledInput label="可信度" value={memoryForm.confidence} onChange={(value) => setMemoryForm({ ...memoryForm, confidence: value })} />
          <LabeledInput label="标签，用逗号分隔" value={memoryForm.tags.join("，")} onChange={(value) => setMemoryForm({ ...memoryForm, tags: splitChineseList(value) })} />
          <LabeledInput label="证据编号，用逗号分隔" value={memoryForm.linked_evidence.join("，")} onChange={(value) => setMemoryForm({ ...memoryForm, linked_evidence: splitChineseList(value) })} />
          <button className="primary-button" onClick={() => void handleCreateMemory()}>
            <FilePlus2 size={17} />
            提交待审阅
          </button>
        </Backdrop>
      )}

      {termFormOpen && (
        <Backdrop onClose={() => setTermFormOpen(false)} title="新建术语条目">
          <LabeledInput label="规范术语" value={termForm.canonical_term} onChange={(value) => setTermForm({ ...termForm, canonical_term: value })} />
          <LabeledInput label="别名，用逗号分隔" value={termForm.aliases.join("，")} onChange={(value) => setTermForm({ ...termForm, aliases: splitChineseList(value) })} />
          <LabeledInput label="领域范围" value={termForm.domain_scope} onChange={(value) => setTermForm({ ...termForm, domain_scope: value })} />
          <LabeledTextarea label="定义" value={termForm.definition} onChange={(value) => setTermForm({ ...termForm, definition: value })} />
          <LabeledInput label="相关术语，用逗号分隔" value={termForm.related_terms.join("，")} onChange={(value) => setTermForm({ ...termForm, related_terms: splitChineseList(value) })} />
          <LabeledInput
            label="易混淆术语，用逗号分隔"
            value={termForm.do_not_confuse_with.join("，")}
            onChange={(value) => setTermForm({ ...termForm, do_not_confuse_with: splitChineseList(value) })}
          />
          <LabeledTextarea label="示例用法" value={termForm.example_usage} onChange={(value) => setTermForm({ ...termForm, example_usage: value })} />
          <LabeledInput label="负责人" value={termForm.owner} onChange={(value) => setTermForm({ ...termForm, owner: value })} />
          <LabeledInput label="审阅人" value={termForm.reviewer} onChange={(value) => setTermForm({ ...termForm, reviewer: value })} />
          <label className="field">
            层级
            <select value={termForm.level} onChange={(event) => setTermForm({ ...termForm, level: event.target.value as "team" | "project" })}>
              <option value="project">项目级</option>
              <option value="team">团队级</option>
            </select>
          </label>
          <button className="primary-button" onClick={() => void handleCreateTerm()}>
            <ClipboardCheck size={17} />
            提交术语审批
          </button>
        </Backdrop>
      )}

      {agentIntakeOpen && (
        <Backdrop onClose={() => setAgentIntakeOpen(false)} title="智能录入">
          <label className="field">
            对象类型
            <select
              value={agentIntakeForm.object_type}
              onChange={(event) => setAgentIntakeForm({ ...agentIntakeForm, object_type: event.target.value as AgentIntakePayload["object_type"] })}
            >
              {["任务", "文献记忆", "实验记录", "讨论记忆", "决策记录", "交接包", "专家声明", "术语条目"].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <LabeledTextarea label="自然语言输入" value={agentIntakeForm.raw_input} onChange={(value) => setAgentIntakeForm({ ...agentIntakeForm, raw_input: value })} />
          <button className="primary-button" onClick={() => void handleAgentIntake()} disabled={isAgentIntakeBusy}>
            <Sparkles size={17} />
            {isAgentIntakeBusy ? "大模型正在分析资料" : "生成结构化草稿"}
          </button>
        </Backdrop>
      )}
      {isAnyModelBusy && (
        <div className="thinking-overlay" aria-live="polite" aria-busy="true">
          <div className="thinking-overlay__card">
            <Loader2 className="spin" size={28} />
            <div>
              <strong>大模型正在思考</strong>
              <span>{globalThinkingLabel}</span>
            </div>
          </div>
        </div>
      )}
        </div>
      </section>
    </main>
  );
}

function matchesSearch(values: string[], normalizedSearch: string) {
  if (!normalizedSearch) return true;
  return values.some((value) => value.toLowerCase().includes(normalizedSearch));
}

function splitChineseList(value: string) {
  return value
    .split(/[，,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}
