import { Brain, CheckCircle2, ClipboardCheck, ClipboardList, FilePlus2, Link2, LogOut, PanelRightOpen, Sparkles, UserRound } from "lucide-react";
import type { ReactNode } from "react";

import type {
  AcceptanceDecisionPayload,
  AgentIntakeResult,
  ApprovalItem,
  AssistantQueryResult,
  ExpertiseMap,
  HandoverBundle,
  PlanningRunResult,
  PlazaProjectCard,
  ProjectLLMDiagnostics,
  RecommendationResult,
  Task,
  TermEntry,
  TMSWorkflow,
  User,
} from "../types";

export function RecommendationPanel({ result, taskTitle }: { result: RecommendationResult; taskTitle: string }) {
  return (
    <section className="recommendation-panel">
      <div>
        <span className="eyebrow">系统推荐结果</span>
        <h3>{taskTitle}</h3>
        <p>{result.message}</p>
      </div>
      <div className="recommendation-list">
        {result.candidates.slice(0, 4).map((candidate) => (
          <div className="candidate-pill" key={candidate.actor_id}>
            <strong>{candidate.actor_name}</strong>
            <span>{candidate.actor_type === "ai" ? "智能协作代理" : "团队成员"} / 评分 {candidate.score}</span>
            <small>{candidate.reasons.join("；")}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

export function AgentIntakePanel({
  result,
  onSupplement,
  onForceExecute,
}: {
  result: AgentIntakeResult;
  onSupplement?: () => void;
  onForceExecute?: () => void;
}) {
  const readiness = result.readiness;
  return (
    <section className="handover-panel">
      <div>
        <span className="eyebrow">智能录入</span>
        <h3>{result.structured_candidate.title}</h3>
        <p>{result.structured_candidate.summary}</p>
      </div>
      {!readiness.ready && (
        <div className="handover-box">
          <strong>{readiness.status === "risky_but_ingestable" ? "当前存在录入风险" : "当前不能直接录入"}</strong>
          <span>{readiness.message}</span>
          <span>{readiness.risk_summary}</span>
          {readiness.risk_items.map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
      )}
      {readiness.supplement_materials.length > 0 && (
        <div className="handover-box">
          <strong>建议补充材料</strong>
          {readiness.supplement_materials.map((item) => (
            <span key={item.item_key}>
              {item.label}：{item.why_needed} 建议操作：{item.recommended_action}
            </span>
          ))}
        </div>
      )}
      {readiness.force_executed && (
        <div className="handover-box">
          <strong>已强制执行入审核层</strong>
          <span>当前条目已进入审核层，但缺失材料仍需后续补齐，不能直接进入共享记忆。</span>
        </div>
      )}
      {!readiness.ready && (
        <div className="approval-actions">
          {onSupplement && (
            <button className="secondary-button" onClick={onSupplement}>
              <FilePlus2 size={17} />
              继续补充输入
            </button>
          )}
          {readiness.status === "risky_but_ingestable" && readiness.force_execute_allowed && !readiness.force_executed && onForceExecute && (
            <button className="secondary-button" onClick={onForceExecute}>
              <Sparkles size={17} />
              强制执行入审核层
            </button>
          )}
        </div>
      )}
      <div className="handover-grid">
        <InfoList title="领域标签" items={result.structured_candidate.domain_tags} />
        <InfoList title="方法标签" items={result.structured_candidate.method_tags} />
        <InfoList title="来源" items={result.structured_candidate.source_refs} />
        <InfoList title="质量提示" items={result.quality_hints.length > 0 ? result.quality_hints : ["暂无额外提示"]} />
      </div>
      {result.saved_review_memory_id && <p className="muted">审核层记忆编号：{result.saved_review_memory_id}</p>}
    </section>
  );
}

export function PlanningPanel({
  result,
  canApprove,
  canForceGenerate,
  isWorking,
  workingLabel,
  llmDiagnostics,
  onApprove,
  onForceGenerate,
  onSupplement,
  onRevise,
  onRegenerate,
}: {
  result: PlanningRunResult;
  canApprove: boolean;
  canForceGenerate: boolean;
  isWorking: boolean;
  workingLabel: string;
  llmDiagnostics?: ProjectLLMDiagnostics;
  onApprove: () => void;
  onForceGenerate: () => void;
  onSupplement: () => void;
  onRevise: () => void;
  onRegenerate: () => void;
}) {
  const readiness = result.plan.planning_readiness;
  const generationLabelMap: Record<string, string> = {
    llm_full: "真实模型规划",
    llm_repaired: "模型结果已局部修复",
    capability_skeleton_fallback: "能力骨架降级生成",
    blocked: "资料不足，未生成正式计划",
  };
  const generationLabel = generationLabelMap[result.plan.generation_source ?? "blocked"] ?? "未知生成模式";
  const latestAttempt = llmDiagnostics?.latest_attempt;
  const configSourceLabel = llmDiagnostics?.effective_config.source === "project_override" ? "项目覆盖配置" : "默认硬编码配置";
  return (
    <section className="handover-panel">
      <div>
        <span className="eyebrow">规划运行</span>
        <h3>计划草稿 v{result.plan.version}</h3>
        <p>{result.analysis_memory.summary}</p>
      </div>
      <div className="handover-box">
        <strong>生成模式</strong>
        <span>{generationLabel}</span>
        {result.plan.generation_diagnostics && result.plan.generation_diagnostics.length > 0 && (
          <span>诊断：{result.plan.generation_diagnostics.join(" / ")}</span>
        )}
        {llmDiagnostics && (
          <span>
            当前生效配置：{configSourceLabel} / {llmDiagnostics.effective_config.provider_name} / {llmDiagnostics.effective_config.chat_model} /{" "}
            {llmDiagnostics.effective_config.api_key_masked}
          </span>
        )}
        {latestAttempt && latestAttempt.status === "failure" && (
          <span>
            最近失败：{latestAttempt.stage} / {latestAttempt.diagnostic_code}
            {latestAttempt.http_status ? ` / 状态码 ${latestAttempt.http_status}` : ""}
            {latestAttempt.response_excerpt ? ` / ${latestAttempt.response_excerpt}` : ""}
          </span>
        )}
      </div>
      {readiness && !readiness.ready && (
        <div className="handover-box">
          <strong>{readiness.status === "risky_but_generatable" ? "当前存在较高风险" : "当前不能生成正式计划"}</strong>
          <span>{readiness.message}</span>
          <span>{readiness.risk_summary}</span>
          {readiness.missing_item_labels.map((item) => (
            <span key={item}>缺少：{item}</span>
          ))}
        </div>
      )}
      {readiness && readiness.supplement_materials.length > 0 && (
        <div className="handover-box">
          <strong>建议补充材料</strong>
          {readiness.supplement_materials.map((item) => (
            <span key={item.item_key}>
              {item.label}：{item.why_needed} 建议操作：{item.recommended_action}
            </span>
          ))}
        </div>
      )}
      {result.plan.is_stale && (
        <div className="handover-box">
          <strong>当前草稿已过期</strong>
          <span>{result.plan.stale_reason || "共享层已更新，请重新生成计划。"}</span>
        </div>
      )}
      {result.plan.generation_mode === "forced_risky" && (
        <div className="handover-box">
          <strong>这是高风险草稿</strong>
          <span>当前草稿仅供讨论和补料，不可直接批准为正式可执行计划。</span>
        </div>
      )}
      <div className="handover-grid">
        <InfoList title="分析摘要" items={[result.analysis_memory.summary]} />
        <InfoList title="计划草稿" items={result.plan.structured_plan.map((task) => `步骤${task.task_index}：${task.title}`)} />
        <InfoList title="负责人" items={result.plan.structured_plan.map((task) => `${task.assigned_user_id} / 审阅 ${task.reviewer_user_id}`)} />
        <InfoList title="交接要求" items={result.plan.structured_plan.map((task) => task.handoff_requirements)} />
      </div>
      {isWorking && (
        <div className="handover-box">
          <strong>大模型正在思考</strong>
          <span>{workingLabel}</span>
        </div>
      )}
      {readiness && !readiness.ready && (
        <div className="approval-actions">
          <button className="secondary-button" onClick={onSupplement} disabled={isWorking}>
            <FilePlus2 size={17} />
            去补充材料
          </button>
          {readiness.status === "risky_but_generatable" && canForceGenerate && (
            <button className="secondary-button" onClick={onForceGenerate} disabled={isWorking}>
              <Sparkles size={17} />
              强行生成高风险草稿
            </button>
          )}
        </div>
      )}
      {canApprove && (
        <div className="approval-actions">
          <button className="primary-button" onClick={onApprove} disabled={isWorking}>
            <ClipboardCheck size={17} />
            批准计划
          </button>
          <button className="secondary-button" onClick={onRevise} disabled={isWorking}>
            <ClipboardList size={17} />
            修改计划
          </button>
          <button className="secondary-button" onClick={onRegenerate} disabled={isWorking}>
            <Sparkles size={17} />
            退回重做
          </button>
        </div>
      )}
    </section>
  );
}

export function LoginScreen({ users, error, onSelectUser }: { users: User[]; error: string | null; onSelectUser: (user: User) => void }) {
  return (
    <main className="login-shell">
      <section className="login-panel">
        <div className="brand login-brand">
          <Brain size={30} />
          <div>
            <strong>研究协作系统</strong>
            <span>先选择用户，再进入授权项目</span>
          </div>
        </div>
        <div>
          <span className="eyebrow">用户登录</span>
          <h1>请选择你的团队身份</h1>
          <p>系统会根据用户身份展示可访问项目，避免跨项目上下文串用。</p>
        </div>
        {error && <div className="login-error">加载失败：{error}</div>}
        <div className="login-user-grid">
          {users.map((user) => (
            <button className="login-user-card" key={user.id} onClick={() => onSelectUser(user)}>
              <UserRound size={22} />
              <strong>{user.name}</strong>
              <span>{user.role}</span>
              <small>可访问项目：{user.project_ids.length} 个</small>
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}

export function PlazaScreen({
  currentUser,
  projects,
  actionStatus,
  onCreateProject,
  onJoinProject,
  onEnterProject,
  onApproveJoinRequest,
  onRejectJoinRequest,
  onLogout,
  children,
}: {
  currentUser: User;
  projects: PlazaProjectCard[];
  actionStatus: string;
  onCreateProject: () => void;
  onJoinProject: (project: PlazaProjectCard) => void;
  onEnterProject: (project: PlazaProjectCard) => void;
  onApproveJoinRequest: (projectId: string, requestId: string) => void;
  onRejectJoinRequest: (projectId: string, requestId: string) => void;
  onLogout: () => void;
  children?: ReactNode;
}) {
  return (
    <main className="plaza-shell">
      <section className="plaza-topbar">
        <div className="brand">
          <Brain size={26} />
          <div>
            <strong>项目广场</strong>
            <span>先加入或创建项目，再进入协作工作台</span>
          </div>
        </div>
        <div className="plaza-actions">
          <div className="current-user-card">
            <UserRound size={18} />
            <div>
              <strong>{currentUser.name}</strong>
              <span>{currentUser.role}</span>
            </div>
          </div>
          <button className="secondary-button" onClick={onCreateProject}>
            <FilePlus2 size={17} />
            新建项目
          </button>
          <button className="text-button" onClick={onLogout}>
            <LogOut size={15} />
            切换用户
          </button>
        </div>
      </section>

      {actionStatus && <section className="notice-strip"><CheckCircle2 size={16} /><span>{actionStatus}</span></section>}

      <section className="plaza-grid">
        {projects.map((project) => (
          <article className="plaza-card" key={project.id}>
            <div className="card-head">
              <span className="type-chip">项目广场</span>
              <span className="state-chip">{project.stage}</span>
            </div>
            <h3>{project.name}</h3>
            <p>{project.summary}</p>
            <div className="meta-line">成员数：{project.member_count}</div>
            <div className="meta-line">加入状态：{project.membership_state}</div>
            <div className="plaza-card-actions">
              {project.membership_state === "member" ? (
                <button className="primary-button" onClick={() => onEnterProject(project)}>
                  进入项目
                </button>
              ) : project.membership_state === "requested" ? (
                <button className="secondary-button" type="button">
                  已申请，等待处理
                </button>
              ) : (
                <button className="primary-button" onClick={() => onJoinProject(project)}>
                  申请加入
                </button>
              )}
            </div>

            {project.pending_join_requests.length > 0 && (
              <div className="pending-requests">
                <strong>待处理申请</strong>
                {project.pending_join_requests.map((request) => (
                  <div className="pending-request-row" key={request.id}>
                    <div>
                      <span>{request.applicant_user_id}</span>
                      <small>{request.message || "未填写说明"}</small>
                    </div>
                    <div className="approval-actions">
                      <button className="mini-approve" onClick={() => onApproveJoinRequest(project.id, request.id)} type="button">
                        同意
                      </button>
                      <button className="mini-reject" onClick={() => onRejectJoinRequest(project.id, request.id)} type="button">
                        拒绝
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </article>
        ))}
        {projects.length === 0 && <EmptyState label="项目广场暂时没有项目，先创建一个吧。" />}
      </section>
      {children}
    </main>
  );
}

export function EmptyState({ label }: { label: string }) {
  return <div className="empty-state">{label}</div>;
}

export function GlobalStatusBanner({
  message,
  tone = "success",
  onClose,
}: {
  message: string;
  tone?: "info" | "success" | "warning" | "error";
  onClose?: () => void;
}) {
  if (!message) return null;

  return (
    <section className={`global-status-banner ${tone}`}>
      <div className="global-status-copy">
        <span className="eyebrow">状态提示</span>
        <strong>{message}</strong>
      </div>
      {onClose && (
        <button className="icon-button" onClick={onClose} aria-label="关闭状态提示" type="button">
          ×
        </button>
      )}
    </section>
  );
}

export function HandoverPanel({ bundle }: { bundle: HandoverBundle }) {
  return (
    <section className="handover-panel">
      <div>
        <span className="eyebrow">交接包草稿</span>
        <h3>{bundle.summary}</h3>
      </div>
      <div className="handover-grid">
        <InfoList title="关键成员" items={bundle.key_members} />
        <InfoList title="关键决策" items={bundle.critical_decisions} />
        <InfoList title="已确认记忆" items={bundle.key_memories} />
        <InfoList title="未决问题" items={bundle.open_questions} />
      </div>
    </section>
  );
}

export function InfoList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="handover-box">
      <strong>{title}</strong>
      {items.length === 0 ? <span>暂无</span> : items.map((item) => <span key={item}>{item}</span>)}
    </div>
  );
}

export function DetailView({
  selected,
  recommendation,
  expertiseMap,
}: {
  selected:
    | { kind: "task"; item: Task }
    | { kind: "memory"; item: import("../types").MemoryItem }
    | { kind: "decision"; item: import("../types").Decision }
    | { kind: "actor"; item: import("../types").Actor }
    | { kind: "workflow"; item: TMSWorkflow }
    | { kind: "term"; item: TermEntry }
    | { kind: "approval"; item: ApprovalItem }
    | { kind: "handover"; item: HandoverBundle }
    | null;
  recommendation: RecommendationResult | null;
  expertiseMap: ExpertiseMap | null;
}) {
  if (!selected) return <p className="muted">请选择一张卡片查看详情。</p>;

  return (
    <div className="detail-stack">
      {"description" in selected.item && <InfoBlock label="说明" value={selected.item.description} />}
      {"summary" in selected.item && <InfoBlock label="摘要" value={selected.item.summary} />}
      {"rationale" in selected.item && <InfoBlock label="依据" value={selected.item.rationale} />}
      {"role" in selected.item && <InfoBlock label="角色" value={selected.item.role} />}
      {"definition" in selected.item && <InfoBlock label="定义" value={selected.item.definition} />}
      {"reason" in selected.item && <InfoBlock label="审批原因" value={selected.item.reason} />}

      {"tags" in selected.item && selected.item.tags.length > 0 && (
        <div>
          <span className="detail-label">标签</span>
          <div className="tag-row">{selected.item.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>
        </div>
      )}

      {"next_action" in selected.item && <InfoBlock label="下一步" value={selected.item.next_action || "等待补充"} />}
      {"next_action_or_implication" in selected.item && typeof selected.item.next_action_or_implication === "string" && (
        <InfoBlock label="影响与下一步" value={selected.item.next_action_or_implication || "暂无"} />
      )}
      {"aliases" in selected.item && selected.item.aliases.length > 0 && <InfoBlock label="别名" value={selected.item.aliases.join(" / ")} />}

      {selected.kind === "actor" &&
        selected.item.expertise_claims.map((claim) => (
          <div className="evidence-box" key={`${claim.domain}-${claim.method}`}>
            <strong>{claim.domain}</strong>
            <span>{claim.method} / {claim.tool}</span>
            <span>验证状态：{claim.verification_status}</span>
            <span>边界：{claim.boundaries}</span>
          </div>
        ))}

      {selected.kind === "workflow" &&
        selected.item.steps.map((step) => (
          <div className="evidence-box" key={step.id}>
            <strong>{step.title}</strong>
            <span>状态：{step.status}</span>
            <span>交付物：{step.required_output}</span>
          </div>
        ))}

      {selected.kind === "memory" && selected.item.version_history.length > 0 && (
        <div className="recommendation-box">
          <div className="detail-label">版本历史</div>
          {selected.item.version_history.map((entry) => (
            <div className="candidate-row" key={`${entry.version}-${entry.updated_at}`}>
              <strong>v{entry.version}</strong>
              <span>{entry.summary}</span>
              <small>{entry.updated_by} / {entry.updated_at}</small>
            </div>
          ))}
        </div>
      )}

      {selected.kind === "task" && recommendation && (
        <div className="recommendation-box">
          <div className="detail-label">系统推荐结果</div>
          <p>{recommendation.message}</p>
          {recommendation.candidates.map((candidate) => (
            <div className="candidate-row" key={candidate.actor_id}>
              <strong>{candidate.actor_name}</strong>
              <span>评分 {candidate.score}</span>
              <small>{candidate.reasons.join("；")}</small>
            </div>
          ))}
        </div>
      )}

      {selected.kind === "approval" && (
        <div className="recommendation-box">
          <div className="detail-label">审批上下文</div>
          <p>状态：{selected.item.status}</p>
          <p>审阅角色：{selected.item.reviewer_role}</p>
          <p>说明：{selected.item.resolution_comment || "尚未处理"}</p>
        </div>
      )}

      {expertiseMap && (
        <div className="trace-box">
          <Link2 size={17} />
          <span>专家地图当前包含 {expertiseMap.nodes.length} 个节点和 {expertiseMap.edges.length} 条关系。</span>
        </div>
      )}
    </div>
  );
}

export function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="detail-label">{label}</span>
      <p className="detail-text">{value}</p>
    </div>
  );
}

export function ProjectAssistantPanel({
  assistantQuery,
  assistantResult,
  isThinking,
  onAssistantQueryChange,
  onSubmit,
  className = "",
}: {
  assistantQuery: string;
  assistantResult: AssistantQueryResult | null;
  isThinking: boolean;
  onAssistantQueryChange: (value: string) => void;
  onSubmit: () => void;
  className?: string;
}) {
  return (
    <div className={`assistant-panel ${className}`.trim()}>
      <span className="eyebrow">项目助手</span>
      <strong>共享层问答</strong>
      <p className="muted">助手默认只读取共享层正式内容，不会越权读取他人未验收资料。</p>
      <textarea
        className="assistant-textarea"
        value={assistantQuery}
        onChange={(event) => onAssistantQueryChange(event.target.value)}
        placeholder="例如：当前项目卡在哪一步，应该找谁处理？"
      />
      <button className="primary-button" onClick={onSubmit} disabled={isThinking}>
        <Sparkles size={17} />
        {isThinking ? "大模型正在组织回答" : "提问项目助手"}
      </button>
      {isThinking && <p className="muted">大模型正在思考，请稍候。</p>}
      {assistantResult && (
        <div className="assistant-answer">
          <strong>回答</strong>
          <p>{assistantResult.answer}</p>
          <small>共享层依据：{assistantResult.retrieved_shared_memory_ids.join("，") || "无"}</small>
          {assistantResult.shared_context_memory_ids && assistantResult.shared_context_memory_ids.length > 0 && (
            <small>共享层上下文：{assistantResult.shared_context_memory_ids.join("，")}</small>
          )}
        </div>
      )}
    </div>
  );
}

export function Backdrop({ children, onClose, title }: { children: ReactNode; onClose: () => void; title: string }) {
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <section className="config-drawer" onClick={(event) => event.stopPropagation()}>
        <header>
          <div>
            <span className="eyebrow">{title}</span>
            <h2>{title}</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label={`关闭${title}`}>
            ×
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}

export function LabeledInput({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="field">
      {label}
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

export function LabeledTextarea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="field">
      {label}
      <textarea value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}
