import { Bot, CheckCircle2, ClipboardCheck, Network, ShieldCheck, UserRound } from "lucide-react";

import type {
  Actor,
  Decision,
  HandoverBundle,
  MemoryItem,
  RecommendationResult,
  Task,
  TMSWorkflow,
} from "../types";

export function TaskCard({
  task,
  owner,
  predecessorTask,
  currentUserId,
  recommendation,
  loading,
  isTerminalTask,
  onSelect,
  onRecommend,
  onOpenSubmit,
  onStartAcceptance,
  onOpenAcceptanceDecision,
}: {
  task: Task;
  owner?: Actor;
  predecessorTask?: Task;
  currentUserId: string;
  recommendation: RecommendationResult | null;
  loading: boolean;
  isTerminalTask?: boolean;
  onSelect: () => void;
  onRecommend: () => void;
  onOpenSubmit: () => void;
  onStartAcceptance: () => void;
  onOpenAcceptanceDecision: (decision: "accepted" | "rejected") => void;
}) {
  return (
    <article className="object-card" onClick={onSelect}>
      <div className="card-head">
        <span className="type-chip">任务</span>
        <span className="state-chip">{task.status}</span>
      </div>
      <h4>{task.title}</h4>
      <p>{task.description}</p>
      <div className="meta-line">负责人：{owner?.name ?? "待分派"}</div>
      <div className="meta-line">截止时间：{task.due_at ?? "待设定"}</div>
      <div className="meta-line">交接要求：{task.handoff_requirements || task.next_action || "待补充"}</div>
      {task.reviewer_user_id && <div className="meta-line">验收人：{task.reviewer_user_id}</div>}
      {task.workflow_gate_status && <div className="meta-line">闭环状态：{task.workflow_gate_status}</div>}
      {predecessorTask && <div className="meta-line">前置任务：{predecessorTask.title} / {predecessorTask.status}</div>}
      <div className="tag-row">{task.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>
      <button className="small-action" onClick={(event) => { event.stopPropagation(); onRecommend(); }}>
        <Network size={16} />
        {loading ? "推荐中" : "推荐专家"}
      </button>
      {currentUserId === task.owner_id && task.status === "assigned" && (
        <button className="small-action" onClick={(event) => { event.stopPropagation(); onOpenSubmit(); }}>
          <CheckCircle2 size={16} />
          我已完成
        </button>
      )}
      {currentUserId === task.reviewer_user_id && (task.status === "submitted" || predecessorTask?.status === "submitted") && (
        <button className="small-action" onClick={(event) => { event.stopPropagation(); onStartAcceptance(); }}>
          <ClipboardCheck size={16} />
          开始验收
        </button>
      )}
      {currentUserId === task.reviewer_user_id && (task.status === "awaiting_acceptance" || predecessorTask?.status === "awaiting_acceptance") && (
        <div className="approval-actions">
          <button className="mini-approve" onClick={(event) => { event.stopPropagation(); onOpenAcceptanceDecision("accepted"); }} type="button">
            验收通过
          </button>
          <button className="mini-reject" onClick={(event) => { event.stopPropagation(); onOpenAcceptanceDecision("rejected"); }} type="button">
            驳回
          </button>
        </div>
      )}
      {recommendation && (
        <div className="inline-recommendation">
          <strong>推荐结果</strong>
          <span>{recommendation.primary_expert?.actor_name ?? "暂无唯一首选，展示候选人"}</span>
          <small>{recommendation.candidates[0]?.reasons.join("；")}</small>
        </div>
      )}
    </article>
  );
}

export function MemoryCard({
  memory,
  canApprove,
  onSelect,
  onApprove,
}: {
  memory: MemoryItem;
  canApprove: boolean;
  onSelect: () => void;
  onApprove: () => void;
}) {
  return (
    <article className="object-card" onClick={onSelect}>
      <div className="card-head">
        <span className="type-chip">{memory.memory_type}</span>
        <span className="state-chip">{memory.review_status}</span>
      </div>
      <h4>{memory.title}</h4>
      <p>{memory.summary}</p>
      <div className="meta-line">来源：{memory.source}</div>
      <div className="meta-line">可信度：{memory.confidence}</div>
      <div className="meta-line">版本：v{memory.version}</div>
      <div className="meta-line">共享状态：{memory.shared ? "已进入共享记忆" : "尚未共享"}</div>
      {canApprove && memory.review_status !== "已确认" && (
        <button className="small-action" onClick={(event) => { event.stopPropagation(); onApprove(); }}>
          <ShieldCheck size={16} />
          批准共享
        </button>
      )}
    </article>
  );
}

export function DecisionCard({ decision, onSelect }: { decision: Decision; onSelect: () => void }) {
  return (
    <article className="object-card" onClick={onSelect}>
      <div className="card-head">
        <span className="type-chip">决策</span>
        <span className="state-chip">{decision.approval_status}</span>
      </div>
      <h4>{decision.title}</h4>
      <p>{decision.rationale}</p>
      <div className="meta-line">证据数量：{decision.linked_evidence.length}</div>
    </article>
  );
}

export function HandoverCard({ bundle, onSelect }: { bundle: HandoverBundle; onSelect: () => void }) {
  return (
    <article className="object-card" onClick={onSelect}>
      <div className="card-head">
        <span className="type-chip">交接包</span>
        <span className="state-chip">{bundle.review_status}</span>
      </div>
      <h4>{bundle.summary}</h4>
      <p>关键决策：{bundle.critical_decisions.join("；") || "暂无"}</p>
      <div className="meta-line">风险项：{bundle.risk_items.length}</div>
    </article>
  );
}

export function ActorCard({ actor, onSelect }: { actor: Actor; onSelect: () => void }) {
  const Icon = actor.actor_type === "ai" ? Bot : UserRound;
  const claim = actor.expertise_claims[0];
  return (
    <article className="object-card actor-card" onClick={onSelect}>
      <div className="card-head">
        <span className="type-chip"><Icon size={14} />{actor.actor_type === "ai" ? "智能协作代理" : "团队成员"}</span>
        <span className="state-chip">{actor.availability}</span>
      </div>
      <h4>{actor.name}</h4>
      <p>{actor.role}</p>
      {claim && <div className="meta-line">专长：{claim.domain} / {claim.method}</div>}
      {!claim && actor.actor_type === "human" && (
        <div className="meta-line">{actor.contribution_summary || "尚未形成项目内正式能力画像"}</div>
      )}
      {actor.actor_type === "ai" && (
        <div className="ai-note">这是可被系统推荐的智能协作代理，只能给出建议、草稿和审阅提示，不能接正式任务、不能审批、不能给最终结论。</div>
      )}
    </article>
  );
}

export function WorkflowCard({
  workflow,
  currentUserId,
  onSelect,
  onAdvance,
}: {
  workflow: TMSWorkflow;
  currentUserId: string;
  onSelect: () => void;
  onAdvance: () => void;
}) {
  const activeStep = workflow.steps.find((step) => step.status === "进行中");
  const completedCount = workflow.steps.filter((step) => step.status === "已完成").length;
  const canAdvance = (workflow.allowed_advance_user_ids ?? []).includes(currentUserId) && workflow.gate_status === "waiting_leader_confirmation";
  const nextOwnerLabel =
    workflow.gate_status === "waiting_downstream_acceptance"
      ? "等待验收人操作"
      : workflow.gate_status === "waiting_leader_confirmation"
        ? "等待组长确认推进"
        : workflow.gate_status === "waiting_upstream_submission"
          ? "等待负责人提交结果"
          : workflow.gate_status === "rework_required"
            ? "等待上游重做后重新提交"
            : "当前闭环已完成";
  return (
    <article className="object-card workflow-card" onClick={onSelect}>
      <div className="card-head">
        <span className="type-chip">{workflow.loop_type}</span>
        <span className="state-chip">{completedCount}/{workflow.steps.length}</span>
      </div>
      <h4>{workflow.title}</h4>
      <p>{workflow.description}</p>
      <div className="workflow-steps">
        {workflow.steps.map((step) => (
          <div className={`workflow-step ${step.status}`} key={step.id}>
            <span>{step.title}</span>
            <small>{step.status}</small>
          </div>
        ))}
      </div>
      <div className="meta-line">当前步骤：{activeStep?.title ?? "闭环已完成或等待复核"}</div>
      <div className="meta-line">{workflow.state_message ?? "该闭环会随任务链自动推进。"}</div>
      <div className="meta-line">当前卡点：{nextOwnerLabel}</div>
      {canAdvance ? (
        <button className="small-action" onClick={(event) => { event.stopPropagation(); onAdvance(); }}>
          <CheckCircle2 size={16} />
          {workflow.advance_action_label || "组长确认推进"}
        </button>
      ) : (
        <div className="meta-line">
          当前不可手动推进：
          {workflow.gate_status === "waiting_downstream_acceptance"
            ? "请先由当前任务的验收人开始验收并提交结论。"
            : workflow.gate_status === "waiting_upstream_submission"
              ? "请先由当前任务负责人提交结果。"
              : workflow.gate_status === "rework_required"
                ? "当前任务已被驳回，需上游重做后重新提交。"
                : "只有在下游验收通过后，组长才能最终确认。"}
        </div>
      )}
    </article>
  );
}
