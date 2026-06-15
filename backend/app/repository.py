from __future__ import annotations

import json
import os
from collections.abc import Iterable

import httpx

from app.agents.planning import build_plan_tasks
from app.agents.prompts import (
    ANALYSIS_AGENT_SYSTEM_PROMPT,
    CAPABILITY_EXTRACTION_SYSTEM_PROMPT,
    DISPATCH_AGENT_SYSTEM_PROMPT,
    PLAN_AGENT_SYSTEM_PROMPT,
)
from app.domain import (
    Actor,
    AcceptanceRecord,
    AgentRunRecord,
    AgentIntakeResult,
    AgentObservation,
    ProjectAssistantSession,
    AcceptanceDecisionInput,
    ApprovalDecisionInput,
    ApprovalItem,
    AuditEvent,
    Decision,
    Evidence,
    ExpertProfileRecord,
    ExpertRelationRecord,
    ExpertiseClaim,
    ExpertiseMap,
    ExpertiseMapEdge,
    ExpertiseMapNode,
    HandoverBundle,
    LLMConfigInput,
    LLMConfigPublic,
    LLMEffectiveConfigDiagnostic,
    LLMAttemptDiagnostic,
    MapView,
    CapabilitySubmission,
    MemoryCreate,
    MemoryItem,
    MemoryUpdateInput,
    MemoryVersionEntry,
    Project,
    ProjectCreateInput,
    ProjectJoinRequest,
    ProjectMember,
    JoinRequestCreateInput,
    JoinRequestRejectInput,
    ProjectSource,
    ProjectLLMDiagnostics,
    ProjectSourceTextInput,
    PlanRecord,
    PlanningReadiness,
    PlanRevisionInput,
    PlanTaskDraft,
    SearchResult,
    SearchResultItem,
    StructuredCandidate,
    SystemModeUpdate,
    SystemState,
    TMSWorkflow,
    Task,
    TaskSubmitInput,
    TermCreateInput,
    TermEntry,
    TrustEvent,
    TrustEventInput,
    TrustRelation,
    User,
)
from app.services.ingest import extract_markdown_text
from app.services.assistant import build_shared_context_ids, build_shared_layer_answer
from app.services.expertise_map import build_expertise_map as build_expertise_map_projection
from app.services.llm_provider import DeepSeekProvider
from app.workflows.governance import ensure_project_leader, list_visible_approvals
from app.workflows.plan_workflow import PlanWorkflowService
from app.workflows.workflow_gate import WorkflowGateService
from app.seed import (
    seed_actors,
    seed_decisions,
    seed_evidence,
    seed_handover_bundles,
    seed_memories,
    seed_project_members,
    seed_projects,
    seed_tasks,
    seed_terms,
    seed_users,
    seed_workflows,
)
from app.tms_helpers import compute_initial_confidence, infer_capability_claims


class InMemoryRepository:
    def __init__(self) -> None:
        self.projects = {project.id: project for project in seed_projects()}
        self.users = {user.id: user for user in seed_users()}
        self.project_members = {member.id: member for member in seed_project_members()}
        self.project_sources: dict[str, ProjectSource] = {}
        self.capability_submissions: dict[str, CapabilitySubmission] = {}
        self.expert_profiles: dict[str, ExpertProfileRecord] = {}
        self.expert_relations: dict[str, ExpertRelationRecord] = {}
        self.agent_runs: dict[str, AgentRunRecord] = {}
        self.plans: dict[str, PlanRecord] = {}
        self.acceptance_records: dict[str, AcceptanceRecord] = {}
        self.assistant_sessions: dict[str, ProjectAssistantSession] = {}
        self.pending_confidence_updates: dict[str, dict[str, object]] = {}
        self.pending_status_updates: dict[str, dict[str, object]] = {}
        self.pending_relation_updates: dict[str, dict[str, object]] = {}
        self.actors = {actor.id: actor for actor in seed_actors()}
        self.tasks = {task.id: task for task in seed_tasks()}
        self.memories = {memory.id: memory for memory in seed_memories()}
        self.decisions = {decision.id: decision for decision in seed_decisions()}
        self.evidence = {evidence.id: evidence for evidence in seed_evidence()}
        self.workflows = {workflow.id: workflow for workflow in seed_workflows()}
        self.terms = {term.id: term for term in seed_terms()}
        self.handover_bundles = {bundle.id: bundle for bundle in seed_handover_bundles()}
        self.llm_configs: dict[str, LLMConfigInput] = {}
        self.project_llm_attempts: dict[str, LLMAttemptDiagnostic] = {}
        self.approval_items: dict[str, ApprovalItem] = {}
        self.trust_events: dict[str, TrustEvent] = {}
        self.agent_observations: dict[str, AgentObservation] = {}
        self.agent_intake_results: dict[str, AgentIntakeResult] = {}
        self.join_requests: dict[str, ProjectJoinRequest] = {}
        self.audit_events: list[AuditEvent] = []
        self.system_states: dict[str, SystemState] = {
            project_id: SystemState(
                mode="normal",
                label="正常模式",
                message="TMS 正常运行，团队记忆、审批队列与任务闭环可用。",
            )
            for project_id in self.projects
        }

    def get_project(self, project_id: str) -> Project | None:
        return self.projects.get(project_id)

    def list_projects(self) -> list[Project]:
        return list(self.projects.values())

    def create_project(self, owner_user_id: str, payload: ProjectCreateInput) -> Project:
        project_id = f"p{len(self.projects) + 1}"
        project = Project(
            id=project_id,
            name=payload.name,
            owner_user_id=owner_user_id,
            stage="立项",
            summary=payload.content,
            status="进行中",
            research_questions=[],
            milestones=["等待资料上传", "等待组队完成", "等待运行 agent 生成计划"],
        )
        self.projects[project.id] = project
        member = ProjectMember(
            id=f"pm-{len(self.project_members) + 1}",
            project_id=project.id,
            user_id=owner_user_id,
            role="leader",
        )
        self.project_members[member.id] = member
        user = self.get_user(owner_user_id)
        if user is not None and project.id not in user.project_ids:
            self.users[owner_user_id] = user.model_copy(update={"project_ids": [*user.project_ids, project.id]})
        self.add_audit_event(
            project_id=project.id,
            action="创建项目",
            object_type="project",
            object_id=project.id,
            message=f"用户创建项目《{project.name}》，等待成员加入和资料上传。",
            actor_id=owner_user_id,
        )
        return project

    def get_actor_for_user(self, user_id: str) -> Actor | None:
        user = self.get_user(user_id)
        if user is None:
            return None
        if user.actor_id and user.actor_id in self.actors:
            return self.actors[user.actor_id]
        return None

    def create_project_source_from_text(self, user_id: str, project_id: str, payload: ProjectSourceTextInput) -> dict[str, object]:
        resolved_title = payload.title.strip() or _derive_title_from_text(payload.content)
        source = ProjectSource(
            id=f"src-{len(self.project_sources) + 1}",
            project_id=project_id,
            uploaded_by=user_id,
            source_type="pasted_text",
            title=resolved_title,
            raw_text=payload.content,
        )
        self.project_sources[source.id] = source
        review_memory = self.create_memory(
            project_id,
            MemoryCreate(
                memory_type="project_seed",
                title=resolved_title,
                summary=_summarize_text(payload.content),
                source=f"项目资料粘贴文本：{resolved_title}",
                confidence="初始导入",
                tags=["项目资料", "待审核"],
            ),
            created_by=user_id,
        )
        updated_source = source.model_copy(update={"status": "structured", "review_memory_id": review_memory.id})
        self.project_sources[source.id] = updated_source
        self.add_audit_event(
            project_id=project_id,
            action="上传项目资料",
            object_type="project_source",
            object_id=source.id,
            message=f"用户上传文字资料《{resolved_title}》，已生成待审阅共享记忆。",
            actor_id=user_id,
        )
        return {
            "id": updated_source.id,
            "project_id": updated_source.project_id,
            "uploaded_by": updated_source.uploaded_by,
            "source_type": updated_source.source_type,
            "title": updated_source.title,
            "status": updated_source.status,
            "review_memory": review_memory,
        }

    def create_project_source_from_pdf(self, user_id: str, project_id: str, file_name: str, extracted_text: str) -> dict[str, object]:
        source = ProjectSource(
            id=f"src-{len(self.project_sources) + 1}",
            project_id=project_id,
            uploaded_by=user_id,
            source_type="pdf",
            title=file_name.rsplit(".", 1)[0],
            file_name=file_name,
            raw_text=extracted_text,
        )
        self.project_sources[source.id] = source
        review_memory = self.create_memory(
            project_id,
            MemoryCreate(
                memory_type="project_seed",
                title=source.title,
                summary=_summarize_text(extracted_text or f"PDF 项目资料：{file_name}"),
                source=f"项目资料 PDF：{file_name}",
                confidence="初始导入",
                tags=["项目资料", "PDF", "待审核"],
            ),
            created_by=user_id,
        )
        updated_source = source.model_copy(update={"status": "structured", "review_memory_id": review_memory.id})
        self.project_sources[source.id] = updated_source
        self.add_audit_event(
            project_id=project_id,
            action="上传项目资料 PDF",
            object_type="project_source",
            object_id=source.id,
            message=f"用户上传 PDF《{file_name}》，已生成待审阅共享记忆。",
            actor_id=user_id,
        )
        return {
            "id": updated_source.id,
            "project_id": updated_source.project_id,
            "uploaded_by": updated_source.uploaded_by,
            "source_type": updated_source.source_type,
            "file_name": updated_source.file_name,
            "title": updated_source.title,
            "status": updated_source.status,
            "review_memory": review_memory,
        }

    def create_project_source_from_markdown(self, user_id: str, project_id: str, file_name: str, markdown_text: str) -> dict[str, object]:
        source = ProjectSource(
            id=f"src-{len(self.project_sources) + 1}",
            project_id=project_id,
            uploaded_by=user_id,
            source_type="markdown",
            title=file_name.rsplit(".", 1)[0],
            file_name=file_name,
            raw_text=markdown_text,
        )
        self.project_sources[source.id] = source
        review_memory = self.create_memory(
            project_id,
            MemoryCreate(
                memory_type="project_seed",
                title=source.title,
                summary=_summarize_text(markdown_text or f"Markdown 项目资料：{file_name}"),
                source=f"项目资料 Markdown：{file_name}",
                confidence="初始导入",
                tags=["项目资料", "Markdown", "待审核"],
            ),
            created_by=user_id,
        )
        updated_source = source.model_copy(update={"status": "structured", "review_memory_id": review_memory.id})
        self.project_sources[source.id] = updated_source
        self.add_audit_event(
            project_id=project_id,
            action="上传项目资料 Markdown",
            object_type="project_source",
            object_id=source.id,
            message=f"用户上传 Markdown《{file_name}》，已生成待审阅共享记忆。",
            actor_id=user_id,
        )
        return {
            "id": updated_source.id,
            "project_id": updated_source.project_id,
            "uploaded_by": updated_source.uploaded_by,
            "source_type": updated_source.source_type,
            "file_name": updated_source.file_name,
            "title": updated_source.title,
            "status": updated_source.status,
            "review_memory": review_memory,
        }

    def run_planning_agent(self, leader_user_id: str, project_id: str, force_generate: bool = False) -> dict[str, object]:
        return _run_planning_agent_v2(self, leader_user_id, project_id, force_generate)

    def approve_plan(self, leader_user_id: str, project_id: str, plan_id: str, comment: str) -> dict[str, object] | None:
        return _approve_plan_v2(self, leader_user_id, project_id, plan_id, comment)

    def revise_plan(self, leader_user_id: str, project_id: str, plan_id: str, payload: PlanRevisionInput) -> PlanRecord | None:
        plan = self.plans.get(plan_id)
        if plan is None or plan.project_id != project_id:
            return None
        revised = plan.model_copy(
            update={
                "leader_feedback": payload.leader_feedback,
                "structured_plan": payload.structured_plan,
                "plan_status": "leader_editing",
            }
        )
        self.plans[plan_id] = revised
        self.add_audit_event(
            project_id=project_id,
            action="修改计划草稿",
            object_type="plan",
            object_id=plan_id,
            message="组长已修改计划草稿，等待重新确认。",
            actor_id=leader_user_id,
        )
        return revised

    def regenerate_plan(self, leader_user_id: str, project_id: str, plan_id: str) -> dict[str, object] | None:
        plan = self.plans.get(plan_id)
        if plan is None or plan.project_id != project_id:
            return None
        previous = plan.model_copy(update={"plan_status": "superseded"})
        self.plans[plan_id] = previous
        regenerated = self.run_planning_agent(leader_user_id, project_id)
        self.add_audit_event(
            project_id=project_id,
            action="退回重做计划",
            object_type="plan",
            object_id=plan_id,
            message="原计划已标记为废弃，并重新运行规划 agent。",
            actor_id=leader_user_id,
        )
        return {
            "previous_plan": previous,
            "new_plan": regenerated["plan"],
            "analysis_memory": regenerated["analysis_memory"],
            "plan_memory": regenerated["plan_memory"],
            "agent_run": regenerated["agent_run"],
        }

    def submit_task_result(
        self,
        user_id: str,
        project_id: str,
        task_id: str,
        payload: TaskSubmitInput,
        result_file_name: str | None = None,
    ) -> dict[str, object] | None:
        task = self.tasks.get(task_id)
        if task is None or task.project_id != project_id:
            return None
        submission_source = f"任务提交：{task.id}"
        if result_file_name:
            submission_source = f"{submission_source} / PDF:{result_file_name}"
        submission_memory = MemoryItem(
            id=f"m{len(self.memories) + 1}",
            project_id=project_id,
            memory_layer="user",
            memory_type="task_submission",
            title=f"{task.title} 提交结果",
            summary=payload.summary,
            source=submission_source,
            confidence="待验证",
            review_status="草稿",
            tags=["任务提交"],
            shared=False,
            owner_user_id=user_id,
            visible_to_user_ids=[user_id, *self.get_project_leader_ids(project_id), *( [task.reviewer_user_id] if task.reviewer_user_id else [] )],
        )
        handoff_memory = MemoryItem(
            id=f"m{len(self.memories) + 2}",
            project_id=project_id,
            memory_layer="user",
            memory_type="handoff_record",
            title=f"{task.title} 交接说明",
            summary=payload.handoff_note,
            source=f"任务交接：{task.id}",
            confidence="待验证",
            review_status="草稿",
            tags=["交接说明"],
            shared=False,
            owner_user_id=user_id,
            visible_to_user_ids=[user_id, *self.get_project_leader_ids(project_id), *( [task.reviewer_user_id] if task.reviewer_user_id else [] )],
        )
        self.memories[submission_memory.id] = submission_memory
        self.memories[handoff_memory.id] = handoff_memory
        self.add_approval_item(
            project_id=project_id,
            object_type="memory",
            object_id=submission_memory.id,
            title=submission_memory.title,
            requested_by=user_id,
            reviewer_role="PI / Team Lead",
            reason="任务提交成果进入共享层前需要组长审批。",
        )
        self.add_approval_item(
            project_id=project_id,
            object_type="memory",
            object_id=handoff_memory.id,
            title=handoff_memory.title,
            requested_by=user_id,
            reviewer_role="PI / Team Lead",
            reason="任务交接记录进入共享层前需要组长审批。",
        )
        updated_task = task.model_copy(
            update={
                "status": "submitted",
                "next_action": payload.handoff_note,
                "outputs": [submission_memory.id, handoff_memory.id],
                "workflow_gate_status": "waiting_downstream_acceptance",
                "leader_confirmation_status": "not_required",
            }
        )
        self.tasks[task.id] = updated_task
        WorkflowGateService(self).mark_submission(project_id, updated_task)
        self.add_audit_event(
            project_id=project_id,
            action="提交任务结果",
            object_type="task",
            object_id=task.id,
            message=f"任务《{task.title}》已提交结果，等待下游验收。",
            actor_id=user_id,
        )
        return {"task": updated_task, "submission_memory": submission_memory, "handoff_memory": handoff_memory}

    def start_acceptance(self, reviewer_user_id: str, project_id: str, current_task_id: str) -> dict[str, object] | None:
        current_task = self.tasks.get(current_task_id)
        if current_task is None or current_task.project_id != project_id:
            return None
        target_task, mode = self._resolve_acceptance_target(current_task)
        if target_task is None:
            return None
        acceptance = AcceptanceRecord(
            id=f"acc-{len(self.acceptance_records) + 1}",
            project_id=project_id,
            task_id=target_task.id,
            submitted_by=target_task.owner_id or "",
            accepted_by=reviewer_user_id,
            decision="started",
            related_user_memory_id=target_task.outputs[0] if target_task.outputs else None,
        )
        self.acceptance_records[acceptance.id] = acceptance
        updated_target = target_task.model_copy(update={"status": "awaiting_acceptance", "workflow_gate_status": "waiting_downstream_acceptance"})
        self.tasks[target_task.id] = updated_target
        if mode == "legacy_downstream":
            WorkflowGateService(self).mark_acceptance_started(project_id, current_task, updated_target)
        self.add_audit_event(
            project_id=project_id,
            action="开始验收",
            object_type="acceptance",
            object_id=acceptance.id,
            message=f"任务《{target_task.title}》进入下游验收。",
            actor_id=reviewer_user_id,
        )
        return {"previous_task": updated_target, "current_task": current_task, "acceptance_record": acceptance}

    def decide_acceptance(
        self,
        reviewer_user_id: str,
        project_id: str,
        current_task_id: str,
        payload: AcceptanceDecisionInput,
    ) -> dict[str, object] | None:
        current_task = self.tasks.get(current_task_id)
        if current_task is None or current_task.project_id != project_id:
            return None
        target_task, mode = self._resolve_acceptance_target(current_task)
        if target_task is None:
            return None
        latest_record = next(
            (
                record
                for record in reversed(list(self.acceptance_records.values()))
                if record.project_id == project_id and record.task_id == target_task.id and record.accepted_by == reviewer_user_id
            ),
            None,
        )
        if latest_record is None:
            return None

        updated_record = latest_record.model_copy(update={"decision": payload.decision, "comment": payload.comment})
        self.acceptance_records[updated_record.id] = updated_record

        if payload.decision == "accepted":
            updated_target = target_task.model_copy(
                update={
                    "status": "awaiting_leader_confirmation",
                    "workflow_gate_status": "waiting_leader_confirmation",
                    "leader_confirmation_status": "pending",
                }
            )
            self.tasks[target_task.id] = updated_target
            if mode == "legacy_downstream":
                updated_current = current_task.model_copy(
                    update={
                        "status": "pending",
                        "workflow_gate_status": "waiting_leader_confirmation",
                        "leader_confirmation_status": "pending",
                    }
                )
                self.tasks[current_task.id] = updated_current
                WorkflowGateService(self).mark_reviewer_decision(project_id, updated_current, updated_target, updated_record)
            else:
                updated_current = updated_target
                WorkflowGateService(self).mark_terminal_reviewer_decision(project_id, updated_target, updated_record)
            self.add_audit_event(
                project_id=project_id,
                action="验收通过",
                object_type="acceptance",
                object_id=updated_record.id,
                message=f"任务《{target_task.title}》已通过下游验收，等待组长最终确认。",
                actor_id=reviewer_user_id,
            )
            return {
                "previous_task": updated_target,
                "current_task": updated_current,
                "acceptance_record": updated_record,
            }

        rejection_memory = MemoryItem(
            id=f"m{len(self.memories) + 1}",
            project_id=project_id,
            memory_layer="event",
            memory_type="rejection_record",
            title=f"{target_task.title} 驳回记录",
            summary=payload.comment,
            source=f"验收驳回：{updated_record.id}",
            confidence="待复核",
            review_status="草稿",
            tags=["驳回记录"],
            shared=False,
            owner_user_id=reviewer_user_id,
            visible_to_user_ids=[target_task.owner_id or "", reviewer_user_id, *self.get_project_leader_ids(project_id)],
        )
        self.memories[rejection_memory.id] = rejection_memory
        updated_target = target_task.model_copy(
            update={
                "status": "rejected",
                "next_action": payload.comment,
                "workflow_gate_status": "rework_required",
                "leader_confirmation_status": "rejected",
            }
        )
        self.tasks[target_task.id] = updated_target
        if mode == "legacy_downstream":
            updated_current = current_task.model_copy(update={"status": "pending", "workflow_gate_status": "waiting_upstream_submission"})
            self.tasks[current_task.id] = updated_current
            WorkflowGateService(self).mark_reviewer_decision(project_id, updated_current, updated_target, updated_record)
        else:
            updated_current = updated_target
            WorkflowGateService(self).mark_terminal_reviewer_rejection(project_id, updated_target, updated_record)
        self.add_audit_event(
            project_id=project_id,
            action="验收驳回",
            object_type="acceptance",
            object_id=updated_record.id,
            message=f"任务《{target_task.title}》被下游验收驳回，需上游重做。",
            actor_id=reviewer_user_id,
        )
        return {
            "previous_task": updated_target,
            "current_task": updated_current,
            "acceptance_record": updated_record,
            "rejection_memory": rejection_memory,
        }

    def _resolve_acceptance_target(self, current_task: Task) -> tuple[Task | None, str]:
        if current_task.status in {"submitted", "awaiting_acceptance"}:
            return current_task, "self_or_terminal"
        previous_task_id = current_task.predecessor_task_id
        if previous_task_id is None:
            return None, "missing"
        previous_task = self.tasks.get(previous_task_id)
        if previous_task is None:
            return None, "missing"
        return previous_task, "legacy_downstream"

    def create_capability_submission(
        self,
        user_id: str,
        project_id: str,
        raw_text: str,
        proof_file_name: str | None,
        proof_text: str,
    ) -> dict[str, object]:
        submission = CapabilitySubmission(
            id=f"cap-{len(self.capability_submissions) + 1}",
            project_id=project_id,
            user_id=user_id,
            raw_text=raw_text,
            proof_file_refs=[proof_file_name] if proof_file_name else [],
            proof_texts=[proof_text] if proof_text else [],
            status="structured",
        )
        self.capability_submissions[submission.id] = submission

        claims = self._extract_capability_claims_with_llm(project_id, raw_text, proof_text) or _infer_capability_claims(raw_text, proof_text)
        confidence_breakdown = _compute_initial_confidence(raw_text, proof_text, self.projects[project_id].summary, claims)
        initial_confidence = round(sum(confidence_breakdown.values()), 3)

        profile_memory = self.create_memory(
            project_id,
            MemoryCreate(
                memory_type="capability_profile",
                title=f"{user_id} 能力画像草稿",
                summary=_summarize_text(raw_text),
                source=f"能力提交：{submission.id}",
                confidence="初始评分",
                tags=["能力画像", "待审核"],
            ),
            created_by=user_id,
            queue_approval=True,
        )
        score_memory = self.create_memory(
            project_id,
            MemoryCreate(
                memory_type="capability_score",
                title=f"{user_id} 初始置信度评分",
                summary=f"初始置信度 {initial_confidence:.2f}；分项：{", ".join(f"{k}:{v:.2f}" for k, v in confidence_breakdown.items())}",
                source=f"能力评分：{submission.id}",
                confidence="初始评分",
                tags=["置信度", "待审核"],
            ),
            created_by=user_id,
            queue_approval=True,
        )

        profile = ExpertProfileRecord(
            id=f"ep-{len(self.expert_profiles) + 1}",
            project_id=project_id,
            user_id=user_id,
            structured_capabilities=claims,
            proof_refs=submission.proof_file_refs,
            initial_confidence=initial_confidence,
            current_confidence=initial_confidence,
            confidence_breakdown=confidence_breakdown,
            status="pending_review",
            network_node_id=f"node-{project_id}-{user_id}",
            review_memory_ids=[profile_memory.id, score_memory.id],
        )
        self.expert_profiles[profile.id] = profile

        relation_snapshot = self._create_relation_snapshot(project_id, user_id, [profile_memory.id, score_memory.id])
        relation_memory = self.create_memory(
            project_id,
            MemoryCreate(
                memory_type="expert_network_snapshot",
                title=f"{user_id} 专家网络快照草稿",
                summary=" / ".join(f"{relation['relation_type']}->{relation['to_user_id']}" for relation in relation_snapshot) or "暂无关系",
                source=f"能力提交：{submission.id}",
                confidence="初始评分",
                tags=["专家网络", "待审核"],
            ),
            created_by=user_id,
            queue_approval=True,
        )
        profile = self.expert_profiles[profile.id].model_copy(update={"review_memory_ids": [profile_memory.id, score_memory.id, relation_memory.id]})
        self.expert_profiles[profile.id] = profile

        self.add_approval_item(
            project_id=project_id,
            object_type="expertise",
            object_id=profile.id,
            title=f"{user_id} 项目内能力画像",
            requested_by=user_id,
            reviewer_role="PI / Team Lead",
            reason="项目内能力画像需要组长审核后，才能进入共享层并参与专家网络计算。",
        )
        self.add_audit_event(
            project_id=project_id,
            action="提交能力申报",
            object_type="capability_submission",
            object_id=submission.id,
            message=f"用户 {user_id} 已提交项目内能力画像，等待组长审核。",
            actor_id=user_id,
        )
        return {
            "submission": submission,
            "expert_profile": profile,
            "review_memories": [profile_memory, score_memory, relation_memory],
            "review_memory_ids": profile.review_memory_ids,
            "relation_snapshot": relation_snapshot,
        }

    def list_users(self) -> list[User]:
        return list(self.users.values())

    def get_user(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    def list_user_projects(self, user_id: str) -> list[Project] | None:
        user = self.get_user(user_id)
        if user is None:
            return None
        member_project_ids = {
            member.project_id
            for member in self.project_members.values()
            if member.user_id == user_id and member.membership_status == "active"
        }
        return [self.projects[project_id] for project_id in member_project_ids if project_id in self.projects]

    def user_can_access_project(self, user_id: str, project_id: str) -> bool:
        return any(
            member.user_id == user_id and member.project_id == project_id and member.membership_status == "active"
            for member in self.project_members.values()
        )

    def is_project_leader(self, user_id: str, project_id: str) -> bool:
        return any(
            member.user_id == user_id and member.project_id == project_id and member.role == "leader" and member.membership_status == "active"
            for member in self.project_members.values()
        )

    def get_project_leader_ids(self, project_id: str) -> list[str]:
        return [
            member.user_id
            for member in self.project_members.values()
            if member.project_id == project_id and member.role == "leader" and member.membership_status == "active"
        ]

    def list_plaza_projects(self, user_id: str) -> list[dict[str, object]]:
        active_project_ids = {
            member.project_id
            for member in self.project_members.values()
            if member.user_id == user_id and member.membership_status == "active"
        }
        pending_project_ids = {
            request.project_id
            for request in self.join_requests.values()
            if request.applicant_user_id == user_id and request.status == "pending"
        }
        cards: list[dict[str, object]] = []
        for project in self.list_projects():
            pending_join_requests = [
                {
                    "id": request.id,
                    "applicant_user_id": request.applicant_user_id,
                    "message": request.message,
                    "created_at": request.created_at,
                }
                for request in self.join_requests.values()
                if request.project_id == project.id and request.status == "pending"
            ]
            if project.id in active_project_ids:
                membership_state = "member"
            elif project.id in pending_project_ids:
                membership_state = "requested"
            else:
                membership_state = "none"
            cards.append(
                {
                    "id": project.id,
                    "name": project.name,
                    "summary": project.summary,
                    "stage": project.stage,
                    "owner_user_id": project.owner_user_id,
                    "member_count": sum(
                        1
                        for member in self.project_members.values()
                        if member.project_id == project.id and member.membership_status == "active"
                    ),
                    "membership_state": membership_state,
                    "pending_join_requests": pending_join_requests if self.is_project_leader(user_id, project.id) else [],
                }
            )
        return cards

    def create_join_request(self, user_id: str, project_id: str, payload: JoinRequestCreateInput) -> ProjectJoinRequest:
        request = ProjectJoinRequest(
            id=f"join-{len(self.join_requests) + 1}",
            project_id=project_id,
            applicant_user_id=user_id,
            message=payload.message,
        )
        self.join_requests[request.id] = request
        self.add_audit_event(
            project_id=project_id,
            action="申请加入项目",
            object_type="join_request",
            object_id=request.id,
            message=f"用户 {user_id} 申请加入项目。",
            actor_id=user_id,
        )
        return request

    def approve_join_request(self, leader_user_id: str, project_id: str, request_id: str) -> ProjectJoinRequest | None:
        request = self.join_requests.get(request_id)
        if request is None or request.project_id != project_id:
            return None
        updated = request.model_copy(update={"status": "approved", "reviewed_by": leader_user_id, "reviewed_at": self._now()})
        self.join_requests[request_id] = updated
        member = ProjectMember(
            id=f"pm-{len(self.project_members) + 1}",
            project_id=project_id,
            user_id=request.applicant_user_id,
            role="member",
        )
        self.project_members[member.id] = member
        user = self.get_user(request.applicant_user_id)
        if user is not None and project_id not in user.project_ids:
            self.users[user.id] = user.model_copy(update={"project_ids": [*user.project_ids, project_id]})
        self.add_audit_event(
            project_id=project_id,
            action="同意入组申请",
            object_type="join_request",
            object_id=request_id,
            message=f"已同意用户 {request.applicant_user_id} 加入项目。",
            actor_id=leader_user_id,
        )
        return updated

    def reject_join_request(self, leader_user_id: str, project_id: str, request_id: str, payload: JoinRequestRejectInput) -> ProjectJoinRequest | None:
        request = self.join_requests.get(request_id)
        if request is None or request.project_id != project_id:
            return None
        updated = request.model_copy(
            update={
                "status": "rejected",
                "reviewed_by": leader_user_id,
                "reviewed_at": self._now(),
                "reject_reason": payload.reason,
            }
        )
        self.join_requests[request_id] = updated
        self.add_audit_event(
            project_id=project_id,
            action="拒绝入组申请",
            object_type="join_request",
            object_id=request_id,
            message=f"已拒绝用户 {request.applicant_user_id} 的入组申请。",
            actor_id=leader_user_id,
        )
        return updated

    def user_has_permission(self, user_id: str, permission: str) -> bool:
        user = self.get_user(user_id)
        if user is None:
            return False
        permission_map = {
            "pi": {"approve_terms", "approve_memory", "approve_decision", "approve_handover", "approve_trust", "approve_expertise"},
            "researcher": {"approve_memory"},
            "student": set(),
        }
        return permission in permission_map.get(user.permission_profile, set())

    def get_task(self, task_id: str) -> Task | None:
        return self.tasks.get(task_id)

    def list_actors(self) -> list[Actor]:
        return list(self.actors.values())

    def list_project_actors(self, project_id: str) -> list[Actor]:
        members = [
            member
            for member in self.project_members.values()
            if member.project_id == project_id and member.membership_status == "active"
        ]
        active_profiles = {profile.user_id: profile for profile in self.list_expert_profiles(project_id) if profile.status == "active"}
        projected: list[Actor] = []
        for member in members:
            user = self.get_user(member.user_id)
            if user is None:
                continue
            seed_actor = self.actors.get(user.actor_id or "")
            projected.append(
                Actor(
                    id=user.id,
                    name=user.name,
                    actor_type="human",
                    role=user.role,
                    expertise_claims=active_profiles.get(user.id).structured_capabilities if user.id in active_profiles else [],
                    trust={},
                    availability=seed_actor.availability if seed_actor is not None else "可协作",
                    affiliation=seed_actor.affiliation if seed_actor is not None else "",
                    verified_expertise_profiles=[active_profiles[user.id].id] if user.id in active_profiles else [],
                    contribution_summary="已形成项目内能力画像" if user.id in active_profiles else "尚未审核项目内能力画像",
                    visibility_scope="project",
                )
            )
        projected.extend(actor for actor in self.actors.values() if actor.actor_type == "ai")
        return projected

    def list_tasks(self, project_id: str) -> list[Task]:
        return [task for task in self.tasks.values() if task.project_id == project_id]

    def list_memories(self, project_id: str, user_id: str | None = None) -> list[MemoryItem]:
        memories = [memory for memory in self.memories.values() if memory.project_id == project_id]
        if user_id is None:
            return memories
        visible: list[MemoryItem] = []
        for memory in memories:
            if memory.memory_layer == "shared":
                visible.append(memory)
                continue
            if user_id in memory.visible_to_user_ids:
                visible.append(memory)
        return visible

    def list_decisions(self, project_id: str) -> list[Decision]:
        return [decision for decision in self.decisions.values() if decision.project_id == project_id]

    def list_evidence(self, project_id: str) -> list[Evidence]:
        return [evidence for evidence in self.evidence.values() if evidence.project_id == project_id]

    def list_workflows(self, project_id: str) -> list[TMSWorkflow]:
        status_priority = {
            "waiting_leader_confirmation": 0,
            "waiting_upstream_submission": 1,
            "waiting_downstream_acceptance": 2,
            "rework_required": 3,
            "readonly": 4,
            "completed": 5,
        }
        return sorted(
            [workflow for workflow in self.workflows.values() if workflow.project_id == project_id],
            key=lambda workflow: (
                status_priority.get(workflow.gate_status, 9),
                0 if workflow.loop_type == "任务执行闭环" else 1,
                workflow.related_object_id or "",
                workflow.id,
            ),
        )

    def list_handover_bundles(self, project_id: str) -> list[HandoverBundle]:
        return [bundle for bundle in self.handover_bundles.values() if bundle.project_id == project_id]

    def list_expert_profiles(self, project_id: str) -> list[ExpertProfileRecord]:
        return [profile for profile in self.expert_profiles.values() if profile.project_id == project_id]

    def list_expert_relations(self, project_id: str) -> list[ExpertRelationRecord]:
        return [relation for relation in self.expert_relations.values() if relation.project_id == project_id]

    def list_terms(self, project_id: str, query: str = "", include_team: bool = False) -> list[TermEntry]:
        query_normalized = query.strip().lower()
        candidates = [
            term
            for term in self.terms.values()
            if term.project_id == project_id or (include_team and term.level == "team")
        ]
        if not query_normalized:
            return candidates
        return [
            term
            for term in candidates
            if query_normalized in term.canonical_term.lower()
            or any(query_normalized in alias.lower() for alias in term.aliases)
            or query_normalized in term.definition.lower()
        ]

    def create_term(self, project_id: str, requested_by: str, payload: TermCreateInput) -> TermEntry:
        term_id = f"term-{len(self.terms) + 1}"
        term = TermEntry(
            id=term_id,
            canonical_term=payload.canonical_term,
            aliases=payload.aliases,
            domain_scope=payload.domain_scope,
            definition=payload.definition,
            related_terms=payload.related_terms,
            do_not_confuse_with=payload.do_not_confuse_with,
            example_usage=payload.example_usage,
            owner=payload.owner,
            reviewer=payload.reviewer,
            level=payload.level,
            project_id=project_id if payload.level == "project" else None,
            review_status="待审阅",
        )
        self.terms[term.id] = term
        self.add_approval_item(
            project_id=project_id,
            object_type="term",
            object_id=term.id,
            title=term.canonical_term,
            requested_by=requested_by,
            reviewer_role="PI / Team Lead",
            reason="术语定义需要组长审批后进入项目治理口径。",
        )
        self.add_audit_event(
            project_id=project_id,
            action="创建术语草稿",
            object_type="term",
            object_id=term.id,
            message=f"术语《{term.canonical_term}》已提交审批。",
            actor_id=requested_by,
        )
        return term

    def add_approval_item(
        self,
        project_id: str,
        object_type: str,
        object_id: str,
        title: str,
        requested_by: str,
        reviewer_role: str,
        reason: str,
    ) -> ApprovalItem:
        item = ApprovalItem(
            id=f"approval-{len(self.approval_items) + 1}",
            project_id=project_id,
            object_type=object_type,
            object_id=object_id,
            title=title,
            requested_by=requested_by,
            reviewer_role=reviewer_role,
            reason=reason,
        )
        self.approval_items[item.id] = item
        return item

    def list_approvals(self, project_id: str, user_id: str | None = None) -> list[ApprovalItem]:
        if user_id is None:
            return [item for item in self.approval_items.values() if item.project_id == project_id]
        return list_visible_approvals(self, user_id, project_id)

    def decide_approval(self, user_id: str, project_id: str, approval_id: str, payload: ApprovalDecisionInput) -> ApprovalItem | None:
        item = self.approval_items.get(approval_id)
        if item is None or item.project_id != project_id:
            return None
        ensure_project_leader(self, user_id, project_id, "审批请求")

        updated = item.model_copy(
            update={
                "status": payload.decision,
                "resolved_by": user_id,
                "resolved_at": self._now(),
                "resolution_comment": payload.comment,
            }
        )
        self.approval_items[approval_id] = updated

        if updated.object_type == "term":
            term = self.terms[updated.object_id]
            self.terms[updated.object_id] = term.model_copy(
                update={"review_status": "已确认" if payload.decision == "approved" else "有争议", "updated_at": self._now()}
            )
        elif updated.object_type == "memory":
            memory = self.memories.get(updated.object_id)
            if memory is not None:
                self.memories[updated.object_id] = memory.model_copy(
                    update={
                        "review_status": "已确认" if payload.decision == "approved" else "有争议",
                        "shared": payload.decision == "approved",
                        "memory_layer": "shared" if payload.decision == "approved" else memory.memory_layer,
                        "visible_to_user_ids": [] if payload.decision == "approved" else memory.visible_to_user_ids,
                        "updated_at": self._now(),
                    }
                )
                if memory.memory_type not in {"analysis_packet", "plan_draft"}:
                    self._mark_draft_plans_stale(project_id, "共享层记忆已更新，计划草稿需要重新校验。")
                if payload.decision == "approved" and updated.object_id in self.pending_confidence_updates:
                    pending = self.pending_confidence_updates[updated.object_id]
                    profile = self.expert_profiles.get(str(pending["profile_id"]))
                    if profile is not None:
                        self.expert_profiles[profile.id] = profile.model_copy(
                            update={
                                "current_confidence": float(pending["new_confidence"]),
                                "updated_at": self._now(),
                            }
                        )
                if payload.decision == "approved" and updated.object_id in self.pending_status_updates:
                    pending_status = self.pending_status_updates[updated.object_id]
                    task = self.tasks.get(str(pending_status["task_id"]))
                    if task is not None:
                        self.tasks[task.id] = task.model_copy(update={"status": "completed"})
                if payload.decision == "approved" and updated.object_id in self.pending_relation_updates:
                    pending_relation = self.pending_relation_updates[updated.object_id]
                    relation = self.expert_relations.get(str(pending_relation["relation_id"]))
                    if relation is not None:
                        self.expert_relations[relation.id] = relation.model_copy(
                            update={"weight": float(pending_relation["new_weight"]), "updated_at": self._now()}
                        )
        elif updated.object_type == "handover":
            bundle = self.handover_bundles.get(updated.object_id)
            if bundle is not None:
                self.handover_bundles[updated.object_id] = bundle.model_copy(
                    update={
                        "review_status": "已确认" if payload.decision == "approved" else "有争议",
                        "published": payload.decision == "approved",
                    }
                )
        elif updated.object_type == "expertise":
            profile = self.expert_profiles.get(updated.object_id)
            if profile is not None:
                profile_status = "active" if payload.decision == "approved" else "pending_review"
                self.expert_profiles[updated.object_id] = profile.model_copy(update={"status": profile_status, "updated_at": self._now()})
                if payload.decision == "approved":
                    self._mark_draft_plans_stale(project_id, "项目内能力画像已更新，计划草稿需要重新校验。")
                    for memory_id in profile.review_memory_ids:
                        memory = self.memories.get(memory_id)
                        if memory is not None:
                            self.memories[memory_id] = memory.model_copy(
                                update={
                                    "review_status": "已确认",
                                    "shared": True,
                                    "memory_layer": "shared",
                                    "visible_to_user_ids": [],
                                    "updated_at": self._now(),
                                }
                            )
                        for approval in list(self.approval_items.values()):
                            if approval.object_type == "memory" and approval.object_id == memory_id and approval.status == "pending":
                                self.approval_items[approval.id] = approval.model_copy(
                                    update={
                                        "status": "approved",
                                        "resolved_by": user_id,
                                        "resolved_at": self._now(),
                                        "resolution_comment": payload.comment or "随能力画像审批自动确认",
                                    }
                                )

        self.add_audit_event(
            project_id=project_id,
            action="审批请求",
            object_type=updated.object_type,
            object_id=updated.object_id,
            message=f"审批结果：{payload.decision}。{payload.comment}".strip(),
            actor_id=user_id,
        )
        return updated

    def advance_workflow(self, user_id: str, project_id: str, workflow_id: str, note: str = "") -> TMSWorkflow | None:
        updated = WorkflowGateService(self).leader_confirm(user_id, project_id, workflow_id, note)
        if updated is None:
            return None
        self.add_audit_event(
            project_id=project_id,
            action="推进 TMS 闭环",
            object_type="workflow",
            object_id=workflow_id,
            message=note.strip() or f"闭环《{updated.title}》已完成组长确认并推进。",
            actor_id=user_id,
        )
        return updated

    def get_system_state(self, project_id: str) -> SystemState:
        return self.system_states.get(
            project_id,
            SystemState(mode="normal", label="正常模式", message="系统正常运行。"),
        )

    def set_system_state(self, project_id: str, update: SystemModeUpdate) -> SystemState:
        state = SystemState(
            mode=update.mode,
            label=update.label,
            message=update.message,
            llm_available=update.llm_available,
            vector_search_available=update.vector_search_available,
            async_queue_available=update.async_queue_available,
            database_writable=update.database_writable,
        )
        self.system_states[project_id] = state
        self.add_audit_event(
            project_id=project_id,
            action="切换系统模式",
            object_type="system_state",
            object_id=update.mode,
            message=update.message,
        )
        return state

    def create_memory(self, project_id: str, payload: MemoryCreate, created_by: str = "system", queue_approval: bool = True) -> MemoryItem:
        memory_id = f"m{len(self.memories) + 1}"
        leader_ids = self.get_project_leader_ids(project_id)
        memory = MemoryItem(
            id=memory_id,
            project_id=project_id,
            memory_layer="review",
            memory_type=payload.memory_type,
            title=payload.title,
            summary=payload.summary,
            source=payload.source,
            source_or_provenance=payload.source,
            confidence=payload.confidence,
            review_status="待审阅",
            tags=payload.tags,
            linked_evidence=payload.linked_evidence,
            linked_decisions=payload.linked_decisions,
            actors_involved=payload.actors_involved,
            next_action_or_implication=payload.next_action_or_implication,
            shared=False,
            owner_user_id=created_by,
            visible_to_user_ids=[created_by, *leader_ids],
        )
        self.memories[memory.id] = memory
        if queue_approval:
            self.add_approval_item(
                project_id=project_id,
                object_type="memory",
                object_id=memory.id,
                title=memory.title,
                requested_by=created_by,
                reviewer_role="PI / Team Lead",
                reason="进入 shared memory 前需要组长审批。",
            )
        self.add_audit_event(
            project_id=project_id,
            action="创建待审阅记忆",
            object_type="memory",
            object_id=memory.id,
            message=f"记忆《{memory.title}》已进入审核层。",
            actor_id=created_by,
        )
        return memory

    def approve_memory(self, project_id: str, memory_id: str, approved_by: str = "system") -> MemoryItem | None:
        memory = self.memories.get(memory_id)
        if memory is None or memory.project_id != project_id:
            return None
        updated = memory.model_copy(
            update={
                "review_status": "已确认",
                "shared": True,
                "memory_layer": "shared",
                "visible_to_user_ids": [],
                "updated_at": self._now(),
            }
        )
        self.memories[memory_id] = updated
        self.add_audit_event(
            project_id=project_id,
            action="批准共享记忆",
            object_type="memory",
            object_id=memory_id,
            message=f"记忆《{updated.title}》已批准进入共享层。",
            actor_id=approved_by,
        )
        return updated

    def update_memory(self, project_id: str, memory_id: str, payload: MemoryUpdateInput, updated_by: str) -> MemoryItem | None:
        memory = self.memories.get(memory_id)
        if memory is None or memory.project_id != project_id:
            return None

        version_entry = MemoryVersionEntry(
            version=memory.version,
            summary=memory.summary,
            next_action_or_implication=memory.next_action_or_implication,
            updated_by=updated_by,
        )
        updated = memory.model_copy(
            update={
                "summary": payload.summary,
                "next_action_or_implication": payload.next_action_or_implication,
                "version": memory.version + 1,
                "version_history": [*memory.version_history, version_entry],
                "review_status": "待审阅",
                "shared": False,
                "updated_at": self._now(),
            }
        )
        self.memories[memory_id] = updated
        self.add_audit_event(
            project_id=project_id,
            action="更新记忆版本",
            object_type="memory",
            object_id=memory_id,
            message=f"记忆《{updated.title}》已更新为 v{updated.version}，等待重新审批。",
            actor_id=updated_by,
        )
        return updated

    def generate_handover(self, project_id: str, requested_by: str = "system") -> HandoverBundle | None:
        project = self.get_project(project_id)
        if project is None:
            return None
        memories = self.list_memories(project_id)
        decisions = self.list_decisions(project_id)
        tasks = self.list_tasks(project_id)
        bundle = HandoverBundle(
            id=f"handover-{project_id}-{len(self.handover_bundles) + 1}",
            project_id=project_id,
            summary=f"{project.name} 当前阶段为{project.stage}，交接包汇总关键记忆、决策、任务和风险。",
            key_members=[actor.name for actor in self.list_actors()[:3]],
            critical_decisions=[decision.title for decision in decisions],
            key_memories=[memory.title for memory in memories if memory.review_status == "已确认"],
            open_questions=[task.next_action for task in tasks if task.next_action],
            risk_items=project.risks,
            review_status="待审阅",
            generated_from=[*self._ids(memories), *self._ids(decisions)],
        )
        self.handover_bundles[bundle.id] = bundle
        self.add_approval_item(
            project_id=project_id,
            object_type="handover",
            object_id=bundle.id,
            title=bundle.summary[:30],
            requested_by=requested_by,
            reviewer_role="PI / Team Lead",
            reason="交接包发布前需要组长确认。",
        )
        self.add_audit_event(
            project_id=project_id,
            action="生成交接包",
            object_type="handover",
            object_id=bundle.id,
            message="系统已生成交接包，等待组长审批。",
            actor_id=requested_by,
        )
        return bundle

    def list_audit_events(self, project_id: str) -> list[AuditEvent]:
        return [event for event in self.audit_events if event.project_id == project_id]

    def add_audit_event(
        self,
        project_id: str,
        action: str,
        object_type: str,
        object_id: str,
        message: str,
        actor_id: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=f"audit-{len(self.audit_events) + 1}",
            project_id=project_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            message=message,
            actor_id=actor_id,
        )
        self.audit_events.insert(0, event)
        return event

    def save_llm_config(self, project_id: str, config: LLMConfigInput) -> LLMConfigPublic:
        self.llm_configs[project_id] = config
        self.add_audit_event(
            project_id=project_id,
            action="保存 LLM 配置",
            object_type="llm_config",
            object_id=project_id,
            message=f"已保存 {config.scope} 范围的 LLM 配置。",
        )
        return LLMConfigPublic(
            scope=config.scope,
            provider_name=config.provider_name,
            base_url=config.base_url,
            api_key_masked=_mask_api_key(config.api_key),
            chat_model=config.chat_model,
            embedding_model=config.embedding_model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    def get_project_llm_diagnostics(self, project_id: str) -> ProjectLLMDiagnostics:
        provider = DeepSeekProvider()
        default_config = provider.config
        llm_config = self.llm_configs.get(project_id)
        source = "project_override" if llm_config is not None and llm_config.api_key.strip() else "default_hardcoded"
        effective = llm_config if source == "project_override" else default_config
        effective_config = LLMEffectiveConfigDiagnostic(
            source=source,
            enabled=bool(effective.api_key.strip()),
            provider_name=effective.provider_name,
            base_url=effective.base_url,
            api_key_masked=_mask_api_key(effective.api_key),
            chat_model=effective.chat_model,
            embedding_model=effective.embedding_model,
            temperature=effective.temperature,
            max_tokens=effective.max_tokens,
        )
        return ProjectLLMDiagnostics(
            effective_config=effective_config,
            latest_attempt=self.project_llm_attempts.get(project_id),
        )

    def record_project_llm_attempt(self, project_id: str, attempt: LLMAttemptDiagnostic) -> LLMAttemptDiagnostic:
        self.project_llm_attempts[project_id] = attempt
        return attempt

    def save_agent_intake_result(self, result: AgentIntakeResult) -> AgentIntakeResult:
        result_id = f"agent-intake-{len(self.agent_intake_results) + 1}"
        saved_memory_id: str | None = None
        if result.readiness.ready or result.readiness.force_executed:
            created_memory = self.create_memory(
                result.structured_candidate.project_id,
                MemoryCreate(
                    memory_type=result.structured_candidate.object_type,
                    title=result.structured_candidate.title,
                    summary=result.structured_candidate.summary,
                    source="；".join(result.structured_candidate.source_refs) if result.structured_candidate.source_refs else "智能录入：缺少来源",
                    confidence=result.structured_candidate.confidence,
                    tags=[
                        *result.structured_candidate.domain_tags,
                        *result.structured_candidate.method_tags,
                        *result.structured_candidate.tool_tags,
                        *(["强制执行"] if result.readiness.force_executed else []),
                    ],
                    next_action_or_implication=(
                        "需补充：" + "；".join(str(item.get("label", "")) for item in result.readiness.supplement_materials)
                        if result.readiness.supplement_materials
                        else result.structured_candidate.suggested_next_action
                    ),
                ),
                created_by=result.created_by,
                queue_approval=True,
            )
            saved_memory_id = created_memory.id
        stored_result = result.model_copy(update={"saved_review_memory_id": saved_memory_id})
        self.agent_intake_results[result_id] = stored_result
        self.add_audit_event(
            project_id=stored_result.structured_candidate.project_id,
            action="生成智能录入草稿",
            object_type="agent_intake",
            object_id=result_id,
            message=(
                f"AI 已生成 {stored_result.structured_candidate.object_type} 草稿，但尚未写入审核层。"
                if not saved_memory_id
                else f"AI 已生成 {stored_result.structured_candidate.object_type} 草稿并写入审核层：{saved_memory_id}"
            ),
            actor_id=stored_result.created_by,
        )
        return stored_result

    def list_agent_observations(self, project_id: str) -> list[AgentObservation]:
        return [item for item in self.agent_observations.values() if item.project_id == project_id]

    def add_agent_observation(self, observation: AgentObservation) -> AgentObservation:
        self.agent_observations[observation.id] = observation
        return observation

    def record_trust_event(self, project_id: str, payload: TrustEventInput, created_by: str) -> dict[str, object]:
        actor = self.actors[payload.target_actor_id]
        current = actor.trust.get(payload.context_domain, {"alpha": 1.0, "beta": 1.0})
        alpha = float(current.get("alpha", 1.0))
        beta = float(current.get("beta", 1.0))

        if payload.review_status == "已确认":
            alpha += payload.weight
        else:
            beta += payload.weight
        balance_after = alpha / (alpha + beta)

        updated_trust = {**actor.trust, payload.context_domain: {"alpha": alpha, "beta": beta}}
        self.actors[actor.id] = actor.model_copy(update={"trust": updated_trust})

        event = TrustEvent(
            id=f"trust-{len(self.trust_events) + 1}",
            project_id=project_id,
            target_actor_id=payload.target_actor_id,
            context_domain=payload.context_domain,
            event_type=payload.event_type,
            weight=payload.weight,
            review_status=payload.review_status,
            source_object_type=payload.source_object_type,
            source_object_id=payload.source_object_id,
            balance_after=balance_after,
        )
        self.trust_events[event.id] = event

        relation = TrustRelation(
            actor_id=payload.target_actor_id,
            context_key=payload.context_domain,
            alpha=alpha,
            beta=beta,
            last_updated_at=self._now(),
            supporting_events=[*self._supporting_events_for(payload.target_actor_id, payload.context_domain), event.id],
        )
        self.add_audit_event(
            project_id=project_id,
            action="记录 trust 事件",
            object_type="trust_event",
            object_id=event.id,
            message=f"{actor.name} 在 {payload.context_domain} 的 trust 事件已记录：{payload.event_type}",
            actor_id=created_by,
        )
        return {"event": event, "relation": relation}

    def build_expertise_map(self, project_id: str, view: MapView) -> ExpertiseMap:
        return build_expertise_map_projection(self, project_id, view)

    def list_plans(self, project_id: str) -> list[PlanRecord]:
        return [plan for plan in self.plans.values() if plan.project_id == project_id]

    def search_project(self, project_id: str, query: str) -> SearchResult:
        state = self.get_system_state(project_id)
        normalized = query.strip().lower()
        haystacks: list[SearchResultItem] = []

        for task in self.list_tasks(project_id):
            if _matches_query(normalized, [task.title, task.description, *task.tags]):
                haystacks.append(
                    SearchResultItem(
                        object_type="task",
                        object_id=task.id,
                        title=task.title,
                        summary=task.description,
                        tags=task.tags,
                        matched_by="keyword",
                        review_status=task.review_status,
                    )
                )
        for memory in self.list_memories(project_id):
            if _matches_query(normalized, [memory.title, memory.summary, memory.source, *memory.tags]):
                haystacks.append(
                    SearchResultItem(
                        object_type="memory",
                        object_id=memory.id,
                        title=memory.title,
                        summary=memory.summary,
                        tags=memory.tags,
                        matched_by="keyword",
                        review_status=memory.review_status,
                    )
                )

        mode = "semantic" if state.vector_search_available else "keyword_fallback"
        message = "已使用语义检索。" if state.vector_search_available else "语义检索暂不可用，已降级为标题 / 摘要 / 标签关键词检索。"
        return SearchResult(mode=mode, query=query, results=haystacks, message=message)

    def answer_project_question(self, user_id: str, project_id: str, query: str) -> ProjectAssistantSession:
        shared_memories = [
            memory
            for memory in self.memories.values()
            if memory.project_id == project_id and memory.memory_layer == "shared"
        ]
        answer, retrieved_ids = build_shared_layer_answer(query, shared_memories)
        shared_context_ids = build_shared_context_ids(shared_memories)
        provider = DeepSeekProvider()
        default_config = provider.config
        llm_config = self.llm_configs.get(project_id)
        effective_api_key = default_config.api_key
        effective_base_url = default_config.base_url
        effective_model = default_config.chat_model
        effective_temperature = default_config.temperature
        effective_max_tokens = default_config.max_tokens
        if llm_config is not None and llm_config.api_key.strip():
            effective_api_key = llm_config.api_key
            effective_base_url = llm_config.base_url
            effective_model = llm_config.chat_model
            effective_temperature = llm_config.temperature
            effective_max_tokens = llm_config.max_tokens
        if effective_api_key.strip():
            shared_context = "\n".join(
                f"- {memory.title}: {memory.summary} (标签: {", ".join(memory.tags) or "无"})"
                for memory in shared_memories[:12]
            )
            system_prompt = (
                "你是项目内 AI 助手，只能基于 memory shared 层回答。"
                "不得引用审核层、用户层或未审阅内容；如果共享层没有依据，请明确说明资料不足。"
                "所有回答必须使用中文，并尽量指出依据来自哪些共享记忆。"
            )
            user_prompt = (
                f"共享层记忆：\n{shared_context or "暂无共享层记忆"}\n\n"
                f"用户问题：{query}\n\n"
                "请基于共享层记忆回答。"
            )



            try:
                answer = provider.generate_text(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    api_key=effective_api_key,
                    base_url=effective_base_url,
                    model=effective_model,
                    temperature=effective_temperature,
                    max_tokens=effective_max_tokens,
                )
                if not retrieved_ids:
                    retrieved_ids = shared_context_ids
            except Exception:
                # If the real provider fails, keep the deterministic shared-layer fallback.
                pass
        if not retrieved_ids and shared_context_ids:
            retrieved_ids = shared_context_ids
        session = ProjectAssistantSession(
            id=f"assistant-{len(self.assistant_sessions) + 1}",
            project_id=project_id,
            user_id=user_id,
            query=query,
            answer=answer,
            retrieved_shared_memory_ids=retrieved_ids,
            shared_context_memory_ids=shared_context_ids,
        )
        self.assistant_sessions[session.id] = session
        self.add_audit_event(
            project_id=project_id,
            action="项目助手问答",
            object_type="assistant_session",
            object_id=session.id,
            message=f"项目助手已回答问题：{query[:40]}",
            actor_id=user_id,
        )
        return session

    def _mark_draft_plans_stale(self, project_id: str, reason: str) -> None:
        for plan in self.plans.values():
            if plan.project_id != project_id or plan.plan_status == "approved":
                continue
            self.plans[plan.id] = plan.model_copy(update={"is_stale": True, "stale_reason": reason})

    def _extract_capability_claims_with_llm(self, project_id: str, raw_text: str, proof_text: str) -> list[ExpertiseClaim] | None:
        runtime = self._resolve_capability_llm_runtime(project_id)
        if not runtime["enabled"]:
            return None
        user_prompt = (
            f"项目摘要：{self.projects[project_id].summary}\n\n"
            f"成员能力自述：\n{raw_text.strip() or "无"}\n\n"
            f"辅助证明材料：\n{proof_text.strip() or "无"}\n\n"
            "请抽取该成员在本项目中的专家能力、方法、工具、边界、可承担角色和自信度，严格输出 JSON。"
        )






        try:
            raw_output = runtime["provider"].generate_text(
                system_prompt=CAPABILITY_EXTRACTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                api_key=str(runtime["api_key"]),
                base_url=str(runtime["base_url"]),
                model=str(runtime["model"]),
                temperature=float(runtime["temperature"]),
                max_tokens=int(runtime["max_tokens"]),
            )
            payload = json.loads(self._normalize_json_text(raw_output))
        except Exception:
            return None
        raw_claims = payload.get("claims", []) if isinstance(payload, dict) else []
        if not isinstance(raw_claims, list):
            return None
        claims: list[ExpertiseClaim] = []
        for item in raw_claims:
            if not isinstance(item, dict):
                continue
            domain = str(item.get("domain") or "").strip()
            method = str(item.get("method") or "").strip()
            tool = str(item.get("tool") or "").strip()
            if not domain or not method or not tool:
                continue
            level = str(item.get("level") or "待确认").strip()
            boundaries = str(item.get("boundaries") or "待组长审核后确认边界").strip()
            supported_roles = item.get("supported_roles", ["执行", "协作"])
            if not isinstance(supported_roles, list) or not supported_roles:
                supported_roles = ["执行", "协作"]
            try:
                confidence = float(item.get("self_confidence", 0.7))
            except (TypeError, ValueError):
                confidence = 0.7
            confidence = max(0.0, min(1.0, confidence))
            evidence = ["能力自述", *(["证明材料"] if proof_text.strip() else [])]
            claims.append(
                ExpertiseClaim(
                    id=None,
                    domain=domain,
                    method=method,
                    tool=tool,
                    level=level,
                    evidence=evidence,
                    recency="2026-06",
                    supported_roles=[str(role) for role in supported_roles if str(role).strip()] or ["执行", "协作"],
                    boundaries=boundaries,
                    self_confidence=confidence,
                    verification_status="待审核",
                    review_status="待审阅",
                )
            )
        return claims or None

    def _resolve_capability_llm_runtime(self, project_id: str) -> dict[str, object]:
        provider = DeepSeekProvider()
        default_config = provider.config
        llm_config = self.llm_configs.get(project_id)

        api_key = default_config.api_key
        base_url = default_config.base_url
        model = default_config.chat_model
        temperature = default_config.temperature
        max_tokens = default_config.max_tokens
        enabled = bool(default_config.api_key.strip()) and "PYTEST_CURRENT_TEST" not in os.environ

        if llm_config is not None and llm_config.api_key.strip():
            api_key = llm_config.api_key
            base_url = llm_config.base_url
            model = llm_config.chat_model
            temperature = llm_config.temperature
            max_tokens = llm_config.max_tokens
            enabled = True

        return {
            "provider": provider,
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "enabled": enabled,
        }

    @staticmethod
    def _normalize_json_text(raw_text: str) -> str:
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines:
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
        return text

    def _supporting_events_for(self, actor_id: str, context_domain: str) -> list[str]:
        return [
            event.id
            for event in self.trust_events.values()
            if event.target_actor_id == actor_id and event.context_domain == context_domain
        ]

    def _ids(self, values: Iterable[object]) -> list[str]:
        return [getattr(value, "id") for value in values if hasattr(value, "id")]

    def _now(self) -> str:
        from app.domain import now_iso

        return now_iso()

    def _create_relation_snapshot(self, project_id: str, user_id: str, evidence_memory_ids: list[str]) -> list[dict[str, object]]:
        relations: list[dict[str, object]] = []
        for member in self.project_members.values():
            if member.project_id != project_id or member.membership_status != "active" or member.user_id == user_id:
                continue
            relation_type = "can_review" if member.role == "leader" else "can_handoff_to"
            relation = ExpertRelationRecord(
                id=f"rel-{len(self.expert_relations) + 1}",
                project_id=project_id,
                from_user_id=user_id,
                to_user_id=member.user_id,
                relation_type=relation_type,
                weight=0.6 if relation_type == "can_review" else 0.45,
                evidence_memory_ids=evidence_memory_ids,
            )
            self.expert_relations[relation.id] = relation
            relations.append(
                {
                    "id": relation.id,
                    "from_user_id": relation.from_user_id,
                    "to_user_id": relation.to_user_id,
                    "relation_type": relation.relation_type,
                    "weight": relation.weight,
                }
            )
        return relations


def _mask_api_key(api_key: str) -> str:
    if len(api_key) <= 6:
        return f"{api_key[:2]}***"
    return f"{api_key[:3]}***{api_key[-2:]}"


def _matches_query(query: str, values: list[str]) -> bool:
    if not query:
        return True
    return any(query in value.lower() for value in values if value)


def _summarize_text(text: str) -> str:
    compact = " ".join(text.split())
    if not compact:
        return "PDF 未提取到可用文本，请补充文字说明。"
    return compact[:180]


def _derive_title_from_text(text: str) -> str:
    compact = " ".join(text.split()).strip()
    if not compact:
        return "未命名资料"
    return compact[:24]


def _infer_capability_claims(raw_text: str, proof_text: str) -> list[object]:
    text = f"{raw_text}\n{proof_text}".lower()
    candidates = [
        ("肿瘤免疫", "流式分析", "FlowJo"),
        ("单细胞分析", "Seurat 流程", "R"),
        ("系统测试", "测试用例", "PDF"),
        ("系统开发", "结构化抽取", "LLM"),
    ]
    claims = []
    from app.domain import ExpertiseClaim

    for domain, method, tool in candidates:
        hits = sum(keyword in text for keyword in [domain.lower(), method.lower(), tool.lower()])
        if hits == 0:
            continue
        claims.append(
            ExpertiseClaim(
                id=None,
                domain=domain,
                method=method,
                tool=tool,
                level="可独立完成" if hits > 1 else "可协作",
                evidence=["能力自述", "证明材料"] if proof_text else ["能力自述"],
                recency="2026-06",
                supported_roles=["执行", "协作"],
                boundaries="待组长审核后确认边界",
                self_confidence=0.55 + min(hits, 2) * 0.15,
                verification_status="待审核",
                review_status="待审阅",
            )
        )
    if claims:
        return claims
    return [
        ExpertiseClaim(
            id=None,
            domain="项目相关能力",
            method="资料整理",
            tool="文本输入",
            level="待确认",
            evidence=["能力自述"],
            recency="2026-06",
            supported_roles=["协作"],
            boundaries="待组长审核后确认边界",
            self_confidence=0.5,
            verification_status="待审核",
            review_status="待审阅",
        )
    ]


def _compute_initial_confidence(raw_text: str, proof_text: str, project_summary: str, claims: list[object]) -> dict[str, float]:
    completeness = 0.25 if len(raw_text.strip()) >= 20 else 0.1
    proof_strength = 0.3 if proof_text.strip() else 0.1
    structure_quality = 0.2 if claims else 0.05
    fit_keywords = sum(keyword in f"{raw_text} {proof_text}".lower() for keyword in project_summary.lower().split()[:6])
    project_fit = min(0.25, 0.08 + fit_keywords * 0.03)
    return {
        "completeness": round(completeness, 3),
        "proof_strength": round(proof_strength, 3),
        "structure_quality": round(structure_quality, 3),
        "project_fit": round(project_fit, 3),
    }


def _build_plan_tasks(project_id: str, active_profiles: list[ExpertProfileRecord]) -> list[PlanTaskDraft]:
    if active_profiles:
        primary = active_profiles[0].user_id
    else:
        primary = "u2"
    reviewer = "u3"
    return [
        PlanTaskDraft(
            task_index=1,
            title="确认项目目标与交付边界",
            goal="整理项目背景、目标、范围、约束和最终交付物，形成可执行的项目输入。",
            assigned_user_id=primary,
            reviewer_user_id=reviewer,
            handoff_requirements="提交项目目标说明、范围边界、交付物清单和关键约束。",
            ddl="T+3 天",
        ),
        PlanTaskDraft(
            task_index=2,
            title="完成系统方案与实现拆解",
            goal="根据共享记忆和专家画像拆解系统模块、任务顺序、负责人和验收关系。",
            assigned_user_id=primary,
            reviewer_user_id=reviewer,
            handoff_requirements="提交结构化任务清单、依赖关系、交接要求和验收标准。",
            ddl="T+5 天",
            predecessor_task_id="task-1",
            dependency_ids=["task-1"],
        ),
        PlanTaskDraft(
            task_index=3,
            title="生成阶段执行建议",
            goal="汇总当前阶段的执行建议、风险点、补料建议和下一轮推进方式。",
            assigned_user_id=primary,
            reviewer_user_id=reviewer,
            handoff_requirements="提交阶段总结、风险清单和下一步门控建议。",
            ddl="T+7 天",
            predecessor_task_id="task-2",
            dependency_ids=["task-2"],
        ),
    ]


def _running_under_pytest() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ


def _resolve_llm_runtime(repo: InMemoryRepository, project_id: str) -> dict[str, object]:
    provider = DeepSeekProvider()
    default_config = provider.config
    llm_config = repo.llm_configs.get(project_id)

    api_key = default_config.api_key
    base_url = default_config.base_url
    model = default_config.chat_model
    temperature = default_config.temperature
    max_tokens = default_config.max_tokens
    provider_name = default_config.provider_name
    config_source = "default_hardcoded"
    enabled = bool(default_config.api_key.strip()) and not _running_under_pytest()

    if llm_config is not None and llm_config.api_key.strip():
        api_key = llm_config.api_key
        base_url = llm_config.base_url
        model = llm_config.chat_model
        temperature = llm_config.temperature
        max_tokens = llm_config.max_tokens
        provider_name = llm_config.provider_name
        config_source = "project_override"
        enabled = True

    return {
        "provider": provider,
        "provider_name": provider_name,
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "config_source": config_source,
        "enabled": enabled,
    }


def _normalize_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _call_llm_json(repo: InMemoryRepository, project_id: str, stage: str, system_prompt: str, user_prompt: str) -> dict[str, object] | None:
    runtime = _resolve_llm_runtime(repo, project_id)
    if not runtime["enabled"]:
        return None
    try:
        raw_text = runtime["provider"].generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            api_key=str(runtime["api_key"]),
            base_url=str(runtime["base_url"]),
            model=str(runtime["model"]),
            temperature=float(runtime["temperature"]),
            max_tokens=max(int(runtime["max_tokens"]), 8192),
        )
        payload = json.loads(_normalize_json_text(raw_text))
        _record_simple_llm_attempt(repo, project_id, runtime, stage, "success", "ok", "LLM 已返回可解析 JSON。")
    except Exception as exc:
        _record_llm_exception(repo, project_id, runtime, stage, exc, "llm_request_failed" if _is_request_exception(exc) else "llm_json_parse_failed")
        return None
    return payload if isinstance(payload, dict) else None


def _record_simple_llm_attempt(
    repo: InMemoryRepository,
    project_id: str,
    runtime: dict[str, object],
    stage: str,
    status: str,
    diagnostic_code: str,
    message: str,
    error_type: str = "",
    http_status: int | None = None,
    response_excerpt: str = "",
) -> None:
    repo.record_project_llm_attempt(
        project_id,
        LLMAttemptDiagnostic(
            stage=stage,
            status=status,
            diagnostic_code=diagnostic_code,
            error_type=error_type,
            message=message,
            http_status=http_status,
            response_excerpt=response_excerpt,
            provider_name=str(runtime.get("provider_name") or ""),
            model=str(runtime.get("model") or ""),
            config_source=str(runtime.get("config_source") or "default_hardcoded"),
        ),
    )


def _is_request_exception(exc: Exception) -> bool:
    return isinstance(exc, (httpx.HTTPError, TimeoutError, ConnectionError))


def _record_llm_exception(
    repo: InMemoryRepository,
    project_id: str,
    runtime: dict[str, object],
    stage: str,
    exc: Exception,
    diagnostic_code: str,
) -> None:
    http_status: int | None = None
    response_excerpt = ""
    if isinstance(exc, httpx.HTTPStatusError):
        http_status = exc.response.status_code
        response_excerpt = exc.response.text[:500]
    _record_simple_llm_attempt(
        repo,
        project_id,
        runtime,
        stage,
        "failure",
        diagnostic_code,
        str(exc)[:500],
        error_type=type(exc).__name__,
        http_status=http_status,
        response_excerpt=response_excerpt,
    )


def _parse_llm_json_payload(raw_text: str) -> dict[str, object] | None:
    payload = json.loads(_normalize_json_text(raw_text))
    return payload if isinstance(payload, dict) else None


def _call_planning_llm_json(
    repo: InMemoryRepository,
    project_id: str,
    system_prompt: str,
    user_prompt: str,
) -> tuple[dict[str, object] | None, str, list[str]]:
    runtime = _resolve_llm_runtime(repo, project_id)
    if not runtime["enabled"]:
        return None, "capability_skeleton_fallback", ["llm_disabled"]

    raw_text = ""
    diagnostics: list[str] = []
    try:
        raw_text = runtime["provider"].generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            api_key=str(runtime["api_key"]),
            base_url=str(runtime["base_url"]),
            model=str(runtime["model"]),
            temperature=float(runtime["temperature"]),
            max_tokens=max(int(runtime["max_tokens"]), 8192),
        )
        payload = _parse_llm_json_payload(raw_text)
        if payload is None:
            raise ValueError("LLM 返回的 planning JSON 不是对象")
        _record_simple_llm_attempt(repo, project_id, runtime, "planning", "success", "ok", "LLM 已返回可解析规划 JSON。")
        return payload, "llm_full", diagnostics
    except Exception as exc:
        if _is_request_exception(exc):
            _record_llm_exception(repo, project_id, runtime, "planning", exc, "llm_request_failed")
            return None, "capability_skeleton_fallback", ["llm_request_failed"]
        diagnostics.append("llm_json_parse_failed")

    retry_prompt = (
        "上一次 planning JSON 无法解析。请从截断处继续补全，或重新输出完整合法 JSON。"
        "只能返回 JSON，不要解释。\n\n"
        f"上一次原始输出：\n{raw_text}\n\n"
        f"原始规划输入：\n{user_prompt}"
    )
    try:
        retry_raw = runtime["provider"].generate_text(
            system_prompt=system_prompt,
            user_prompt=retry_prompt,
            api_key=str(runtime["api_key"]),
            base_url=str(runtime["base_url"]),
            model=str(runtime["model"]),
            temperature=float(runtime["temperature"]),
            max_tokens=max(int(runtime["max_tokens"]), 8192),
        )
        payload = _parse_llm_json_payload(raw_text + retry_raw)
        if payload is None:
            payload = _parse_llm_json_payload(retry_raw)
        if payload is None:
            raise ValueError("LLM 续写后的 planning JSON 不是对象")
        diagnostics.append("llm_retry_compact_stitched")
        _record_simple_llm_attempt(repo, project_id, runtime, "planning", "success", "ok", "LLM planning JSON 已通过续写补全。")
        return payload, "llm_repaired", diagnostics
    except Exception as exc:
        if _is_request_exception(exc):
            _record_llm_exception(repo, project_id, runtime, "planning", exc, "llm_request_failed")
            diagnostics.append("llm_request_failed")
        else:
            _record_llm_exception(repo, project_id, runtime, "planning", exc, "llm_json_parse_failed")
        return None, "capability_skeleton_fallback", diagnostics


def _build_shared_memory_context(shared_memories: list[MemoryItem]) -> str:
    if not shared_memories:
        return "暂无共享层记忆"
    return "\n".join(
        f"- {memory.title}: {memory.summary} (标签: {', '.join(memory.tags) or '无'})"
        for memory in shared_memories[:12]
    )


def _build_profile_context(active_profiles: list[ExpertProfileRecord]) -> str:
    if not active_profiles:
        return "暂无已审核项目内能力画像"
    lines: list[str] = []
    for profile in active_profiles:
        claim_parts: list[str] = []
        for claim in profile.structured_capabilities[:4]:
            roles = " / ".join(claim.supported_roles) if claim.supported_roles else "未说明"
            claim_parts.append(
                f"{claim.domain}；方法：{claim.method}；工具：{claim.tool}；角色：{roles}；边界：{claim.boundaries}"
            )
        lines.append(f"- {profile.user_id}: 置信度 {profile.current_confidence:.2f}; 能力画像 {' | '.join(claim_parts) or '信息不足'}")
    return "\n".join(lines)


def _fallback_analysis_payload(
    repo: InMemoryRepository,
    project_id: str,
    shared_memories: list[MemoryItem],
    active_profiles: list[ExpertProfileRecord],
) -> dict[str, object]:
    capability_coverage = [
        {
            "user_id": profile.user_id,
            "capabilities": [claim.domain for claim in profile.structured_capabilities[:3]] or ["信息不足"],
        }
        for profile in active_profiles
    ]
    capability_gaps = ["统计审阅"] if not any("统计" in " ".join(item["capabilities"]) for item in capability_coverage) else []
    current_blockers: list[str] = []
    if not shared_memories:
        current_blockers.append("共享层资料不足")
    if not active_profiles:
        current_blockers.append("尚未形成正式专家画像")
    return {
        "project_summary": repo.projects[project_id].summary or repo.projects[project_id].name,
        "confirmed_inputs": [memory.title for memory in shared_memories[:6]] or ["信息不足"],
        "capability_coverage": capability_coverage,
        "capability_gaps": capability_gaps or ["信息不足"],
        "current_blockers": current_blockers or ["暂无"],
        "planning_focus": ["确认项目目标", "拆解任务链路"],
        "risk_notes": ["若共享层信息不完整，计划只能作为草稿"],
    }


def _analysis_payload_to_summary(payload: dict[str, object]) -> str:
    parts = [str(payload.get("project_summary") or "信息不足")]
    confirmed_inputs = [str(item) for item in payload.get("confirmed_inputs", []) if str(item).strip()]
    if confirmed_inputs:
        parts.append("确认输入：" + "；".join(confirmed_inputs[:4]))
    coverage_items = payload.get("capability_coverage", [])
    if isinstance(coverage_items, list) and coverage_items:
        formatted: list[str] = []
        for item in coverage_items[:4]:
            if isinstance(item, dict):
                user_id = str(item.get("user_id") or "unknown")
                capabilities = item.get("capabilities", [])
                if not isinstance(capabilities, list):
                    capabilities = []
                formatted.append(f"{user_id}:{'/'.join(str(cap) for cap in capabilities[:3]) or '信息不足'}")
        if formatted:
            parts.append("能力覆盖：" + "；".join(formatted))
    risk_notes = [str(item) for item in payload.get("risk_notes", []) if str(item).strip()]
    if risk_notes:
        parts.append("风险：" + "；".join(risk_notes[:3]))
    return " ".join(parts)


def _coerce_plan_task(item: dict[str, object], fallback_reviewer: str, task_index: int) -> PlanTaskDraft:
    predecessor = item.get("predecessor_task_id")
    if predecessor is None:
        predecessor = item.get("predecessor_task_temp_ref")
    dependency_ids = item.get("dependency_ids", [])
    if not isinstance(dependency_ids, list):
        dependency_ids = []
    return PlanTaskDraft(
        task_index=int(item.get("task_index") or task_index),
        title=str(item.get("title") or f"步骤 {task_index}"),
        goal=str(item.get("goal") or "信息不足"),
        assigned_user_id=str(item.get("assigned_user_id") or "u2"),
        reviewer_user_id=str(item.get("reviewer_user_id") or fallback_reviewer or "u3"),
        handoff_requirements=str(item.get("handoff_requirements") or "提交阶段成果并说明交接依据"),
        ddl=str(item.get("ddl") or "T+3 天"),
        predecessor_task_id=str(predecessor) if predecessor else None,
        dependency_ids=[str(dep) for dep in dependency_ids if str(dep).strip()],
    )


def _fallback_plan_payload(
    repo: InMemoryRepository,
    project_id: str,
    active_profiles: list[ExpertProfileRecord],
    reviewer: str,
) -> dict[str, object]:
    tasks = build_plan_tasks(project_id, active_profiles, reviewer)
    return {
        "plan_title": f"{repo.projects[project_id].name} 协作计划",
        "plan_summary": "基于共享层资料和已审核专家画像生成线性协作计划草稿。",
        "execution_mode": "linear",
        "tasks": tasks,
        "risk_notes": ["当前为线性 V1 闭环，暂不展开复杂 DAG。"],
    }


def _plan_payload_to_summary(plan: PlanRecord) -> str:
    task_summary = "；".join(f"步骤{task.task_index}:{task.title}->{task.assigned_user_id}" for task in plan.structured_plan)
    prefix = plan.plan_summary or plan.plan_title or "计划草稿"
    return f"{prefix} {task_summary}".strip()


def _build_fallback_dispatch_item(draft: PlanTaskDraft) -> dict[str, object]:
    return {
        "task_index": draft.task_index,
        "assigned_user_id": draft.assigned_user_id,
        "reviewer_user_id": draft.reviewer_user_id,
        "title": draft.title,
        "goal": draft.goal,
        "ddl": draft.ddl,
        "submission_requirements": ["上传 PDF 或粘贴文字成果", "说明完成依据"],
        "handoff_target_user_id": draft.reviewer_user_id,
        "acceptance_standard": ["成果与任务目标一致", "来源依据清晰", "交接说明完整"],
        "dispatch_message": f"请完成《{draft.title}》，DDL 为 {draft.ddl}，提交后由 {draft.reviewer_user_id} 验收。",
    }


def _generate_analysis_payload(
    repo: InMemoryRepository,
    project_id: str,
    shared_memories: list[MemoryItem],
    active_profiles: list[ExpertProfileRecord],
) -> dict[str, object]:
    fallback = _fallback_analysis_payload(repo, project_id, shared_memories, active_profiles)
    payload = _call_llm_json(
        repo,
        project_id,
        "analysis",
        ANALYSIS_AGENT_SYSTEM_PROMPT,
        (
            f"项目名称：{repo.projects[project_id].name}\n"
            f"项目摘要：{repo.projects[project_id].summary}\n\n"
            f"共享层资料：\n{_build_shared_memory_context(shared_memories)}\n\n"
            f"正式专家画像：\n{_build_profile_context(active_profiles)}"
        ),
    )
    if payload is None:
        return fallback
    merged = {**fallback, **payload}
    coverage = merged.get("capability_coverage", fallback["capability_coverage"])
    if not isinstance(coverage, list):
        coverage = fallback["capability_coverage"]
    merged["capability_coverage"] = coverage
    for key in ["confirmed_inputs", "capability_gaps", "current_blockers", "planning_focus", "risk_notes"]:
        value = merged.get(key, fallback[key])
        if not isinstance(value, list):
            value = fallback[key]
        merged[key] = [str(item) for item in value if str(item).strip()] or fallback[key]
    merged["project_summary"] = str(merged.get("project_summary") or fallback["project_summary"])
    return merged


def _generate_plan_payload(
    repo: InMemoryRepository,
    project_id: str,
    analysis_payload: dict[str, object],
    shared_memories: list[MemoryItem],
    active_profiles: list[ExpertProfileRecord],
    reviewer: str,
) -> tuple[dict[str, object], str, list[str]]:
    fallback = _fallback_plan_payload(repo, project_id, active_profiles, reviewer)
    user_prompt = (
        f"项目名称：{repo.projects[project_id].name}\n"
        f"项目摘要：{repo.projects[project_id].summary}\n\n"
        f"analysis_packet：\n{json.dumps(analysis_payload, ensure_ascii=False, indent=2)}\n\n"
        f"共享层资料：\n{_build_shared_memory_context(shared_memories)}\n\n"
        f"正式专家画像：\n{_build_profile_context(active_profiles)}\n\n"
        f"组长 reviewer 默认是：{reviewer}"
    )
    payload, source, diagnostics = _call_planning_llm_json(repo, project_id, PLAN_AGENT_SYSTEM_PROMPT, user_prompt)
    if payload is None:
        return fallback, "capability_skeleton_fallback", diagnostics or ["llm_disabled"]
    raw_tasks = payload.get("tasks", [])
    if not isinstance(raw_tasks, list) or not raw_tasks:
        return fallback, "capability_skeleton_fallback", [*diagnostics, "llm_plan_tasks_empty"]
    tasks = [_coerce_plan_task(item, reviewer, index + 1) for index, item in enumerate(raw_tasks) if isinstance(item, dict)]
    if not tasks:
        return fallback, "capability_skeleton_fallback", [*diagnostics, "llm_plan_tasks_invalid"]
    risk_notes = payload.get("risk_notes", fallback["risk_notes"])
    if not isinstance(risk_notes, list):
        risk_notes = fallback["risk_notes"]
    return {
        "plan_title": str(payload.get("plan_title") or fallback["plan_title"]),
        "plan_summary": str(payload.get("plan_summary") or fallback["plan_summary"]),
        "execution_mode": "linear",
        "tasks": tasks,
        "risk_notes": [str(item) for item in risk_notes if str(item).strip()] or fallback["risk_notes"],
    }, source, diagnostics


def _generate_dispatch_payload(repo: InMemoryRepository, project_id: str, plan: PlanRecord) -> dict[str, object]:
    fallback_tasks = [_build_fallback_dispatch_item(task) for task in plan.structured_plan]
    fallback = {
        "dispatch_batch_title": f"{plan.plan_title or repo.projects[project_id].name} 任务发放批次",
        "tasks": fallback_tasks,
    }
    runtime = _resolve_llm_runtime(repo, project_id)
    if not runtime["enabled"]:
        _record_simple_llm_attempt(repo, project_id, runtime, "dispatch", "failure", "llm_disabled", "当前未启用 LLM，使用规则兜底发放。")
        return fallback
    user_prompt = (
        f"项目名称：{repo.projects[project_id].name}\n"
        f"正式计划标题：{plan.plan_title}\n"
        f"正式计划摘要：{plan.plan_summary}\n\n"
        f"结构化任务：\n{json.dumps([task.model_dump() for task in plan.structured_plan], ensure_ascii=False, indent=2)}"
    )





    raw_text = ""
    try:
        raw_text = runtime["provider"].generate_text(
            system_prompt=DISPATCH_AGENT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            api_key=str(runtime["api_key"]),
            base_url=str(runtime["base_url"]),
            model=str(runtime["model"]),
            temperature=float(runtime["temperature"]),
            max_tokens=max(int(runtime["max_tokens"]), 8192),
        )
        payload = json.loads(_normalize_json_text(raw_text))
    except Exception:
        try:
            retry_prompt = (
                f"上一次返回的 JSON 无法解析，请从截断处继续补全，或重新输出完整合法 JSON，不要解释。\n{raw_text}\n\n"
                f"项目名称：{repo.projects[project_id].name}\n"
                f"正式计划标题：{plan.plan_title}\n"
                f"正式计划摘要：{plan.plan_summary}\n"
                f"结构化任务：\n{json.dumps([task.model_dump() for task in plan.structured_plan], ensure_ascii=False, indent=2)}\n"
                "必须只返回 JSON 对象。"
            )








            retry_raw = runtime["provider"].generate_text(
                system_prompt=DISPATCH_AGENT_SYSTEM_PROMPT,
                user_prompt=retry_prompt,
                api_key=str(runtime["api_key"]),
                base_url=str(runtime["base_url"]),
                model=str(runtime["model"]),
                temperature=float(runtime["temperature"]),
                max_tokens=max(int(runtime["max_tokens"]), 8192),
            )
            payload = json.loads(_normalize_json_text(raw_text + retry_raw))
            _record_simple_llm_attempt(repo, project_id, runtime, "dispatch", "success", "ok", "LLM 已返回可解析 JSON。")
        except Exception:
            _record_simple_llm_attempt(repo, project_id, runtime, "dispatch", "failure", "llm_json_parse_failed", "Dispatch JSON 仍无法解析，已使用规则兜底发放。")
            return fallback
    if not isinstance(payload, dict):
        return fallback
    raw_tasks = payload.get("tasks", [])
    if not isinstance(raw_tasks, list) or not raw_tasks:
        return fallback
    normalized: list[dict[str, object]] = []
    for index, item in enumerate(raw_tasks):
        if not isinstance(item, dict):
            continue
        fallback_item = fallback_tasks[index] if index < len(fallback_tasks) else _build_fallback_dispatch_item(plan.structured_plan[index])
        normalized.append(
            {
                "task_index": int(item.get("task_index") or fallback_item["task_index"]),
                "assigned_user_id": str(item.get("assigned_user_id") or fallback_item["assigned_user_id"]),
                "reviewer_user_id": str(item.get("reviewer_user_id") or fallback_item["reviewer_user_id"]),
                "title": str(item.get("title") or fallback_item["title"]),
                "goal": str(item.get("goal") or fallback_item["goal"]),
                "ddl": str(item.get("ddl") or fallback_item["ddl"]),
                "submission_requirements": item.get("submission_requirements") if isinstance(item.get("submission_requirements"), list) else fallback_item["submission_requirements"],
                "handoff_target_user_id": str(item.get("handoff_target_user_id") or fallback_item["handoff_target_user_id"]),
                "acceptance_standard": item.get("acceptance_standard") if isinstance(item.get("acceptance_standard"), list) else fallback_item["acceptance_standard"],
                "dispatch_message": str(item.get("dispatch_message") or fallback_item["dispatch_message"]),
            }
        )
    if not normalized:
        return fallback
    return {
        "dispatch_batch_title": str(payload.get("dispatch_batch_title") or fallback["dispatch_batch_title"]),
        "tasks": normalized,
    }


def _shared_memory_signature(shared_memories: list[MemoryItem]) -> str:
    return "|".join(f"{memory.id}:{memory.version}:{memory.updated_at}" for memory in shared_memories)


def _evaluate_planning_readiness(
    project: Project,
    shared_memories: list[MemoryItem],
    active_profiles: list[ExpertProfileRecord],
) -> PlanningReadiness:
    if not shared_memories:
        return PlanningReadiness(
            ready=False,
            status="blocked",
            missing_items=["shared_project_materials"],
            missing_item_labels=["已审批项目资料"],
            satisfied_items=[],
            message="共享层尚无正式项目资料，不能生成可执行计划。",
            risk_summary="风险：缺少已审批共享层资料，计划 agent 没有可靠事实依据。",
            risk_items=["项目目标、范围、交付物和约束尚未进入共享层。"],
            supplement_materials=[
                {
                    "type": "project_source",
                    "label": "上传或粘贴项目目标、范围、交付物、时间约束和治理约束，并由组长审批进入共享层。",
                    "material_id": "",
                }
            ],
            force_generate_allowed=False,
        )

    if not active_profiles:
        return PlanningReadiness(
            ready=False,
            status="risky_but_generatable",
            missing_items=["approved_project_capabilities"],
            missing_item_labels=["已审批项目内能力画像"],
            satisfied_items=["shared_project_materials"],
            message="共享层已有项目资料，但尚无已审批项目内能力画像。",
            risk_summary="风险：可以强制生成高风险草稿，但任务分配缺少项目内专家能力依据。",
            risk_items=["缺少已审批项目内能力画像，专家分配和验收人选择可信度不足。"],
            supplement_materials=[
                {
                    "type": "capability_profile",
                    "label": "至少提交并审批核心成员的项目内能力、可承担角色、边界和置信度。",
                    "material_id": "",
                }
            ],
            force_generate_allowed=True,
        )

    return PlanningReadiness(
        ready=True,
        status="ready",
        missing_items=[],
        missing_item_labels=[],
        satisfied_items=["shared_project_materials", "approved_project_capabilities"],
        message=f"《{project.name}》已有共享层资料和已审批项目内能力画像，可以生成计划草稿。",
        risk_summary="当前资料满足生成线性计划草稿的最低条件。",
        risk_items=[],
        supplement_materials=[],
        force_generate_allowed=False,
    )


def _blocked_or_risky_plan_payload(repo: InMemoryRepository, project_id: str, readiness: PlanningReadiness) -> dict[str, object]:
    return {
        "plan_title": f"资料不足：{repo.projects[project_id].name} 计划暂不能直接生成",
        "plan_summary": readiness.risk_summary or readiness.message,
        "execution_mode": "linear",
        "tasks": [],
        "risk_notes": readiness.risk_items or [readiness.message],
    }



def _run_planning_agent_v2(
    self: InMemoryRepository,
    leader_user_id: str,
    project_id: str,
    force_generate: bool = False,
) -> dict[str, object]:
    shared_memories = [memory for memory in self.memories.values() if memory.project_id == project_id and memory.shared]
    active_profiles = [profile for profile in self.list_expert_profiles(project_id) if profile.status == "active"]
    readiness = _evaluate_planning_readiness(self.projects[project_id], shared_memories, active_profiles)
    runtime = _resolve_llm_runtime(self, project_id)
    agent_run = AgentRunRecord(
        id=f"ar-{len(self.agent_runs) + 1}",
        project_id=project_id,
        triggered_by=leader_user_id,
        model_name=str(runtime["provider_name"]),
        run_type="project_bootstrap_or_replan",
        status="running",
    )
    self.agent_runs[agent_run.id] = agent_run

    analysis_payload = _generate_analysis_payload(self, project_id, shared_memories, active_profiles)
    analysis_memory = self.create_memory(
        project_id,
        MemoryCreate(
            memory_type="analysis_packet",
            title=f"{self.projects[project_id].name} 分析结果草稿",
            summary=_analysis_payload_to_summary(analysis_payload),
            source=f"AgentRun:{agent_run.id}",
            confidence="待组长审核",
            tags=["analysis_packet", "待审阅"],
        ),
        created_by=leader_user_id,
        queue_approval=True,
    )

    reviewer = self.get_project_leader_ids(project_id)[0] if self.get_project_leader_ids(project_id) else leader_user_id
    generation_mode = "normal"
    generation_source = "blocked"
    generation_diagnostics: list[str] = []
    if readiness.status == "blocked":
        plan_payload = _blocked_or_risky_plan_payload(self, project_id, readiness)
        generation_mode = "blocked"
        generation_diagnostics = ["planning_readiness_blocked"]
    elif readiness.status == "risky_but_generatable" and not force_generate:
        plan_payload = _blocked_or_risky_plan_payload(self, project_id, readiness)
        generation_mode = "blocked"
        generation_diagnostics = ["planning_readiness_risky_requires_confirmation"]
    else:
        plan_payload, generation_source, generation_diagnostics = _generate_plan_payload(
            self,
            project_id,
            analysis_payload,
            shared_memories,
            active_profiles,
            reviewer,
        )
        if readiness.status == "risky_but_generatable" and force_generate:
            generation_mode = "forced_risky"
            if readiness.risk_summary and readiness.risk_summary not in plan_payload["risk_notes"]:
                plan_payload["risk_notes"] = [readiness.risk_summary, *list(plan_payload["risk_notes"])]
    plan = PlanRecord(
        id=f"plan-{len(self.plans) + 1}",
        project_id=project_id,
        version=1 + sum(existing.project_id == project_id for existing in self.plans.values()),
        plan_title=str(plan_payload["plan_title"]),
        plan_summary=str(plan_payload["plan_summary"]),
        execution_mode="linear",
        generated_by_agent_run_id=agent_run.id,
        structured_plan=list(plan_payload["tasks"]),
        risk_notes=list(plan_payload["risk_notes"]),
        planning_readiness=readiness,
        generation_mode=generation_mode,
        generation_source=generation_source,
        generation_diagnostics=generation_diagnostics,
        based_on_memory_ids=[memory.id for memory in shared_memories],
        shared_snapshot_signature=_shared_memory_signature(shared_memories),
    )
    self.plans[plan.id] = plan

    plan_memory = self.create_memory(
        project_id,
        MemoryCreate(
            memory_type="plan_draft",
            title=f"{plan.plan_title} v{plan.version}",
            summary=_plan_payload_to_summary(plan),
            source=f"AgentRun:{agent_run.id}",
            confidence="待组长审核",
            tags=["plan_draft", "待审阅"],
        ),
        created_by=leader_user_id,
        queue_approval=True,
    )
    completed_run = agent_run.model_copy(
        update={
            "status": "completed",
            "analysis_output_memory_id": analysis_memory.id,
            "plan_output_memory_id": plan_memory.id,
        }
    )
    self.agent_runs[agent_run.id] = completed_run
    self.add_audit_event(
        project_id=project_id,
        action="运行规划 Agent",
        object_type="agent_run",
        object_id=agent_run.id,
        message="分析 agent 与计划 agent 已生成待审核草稿。",
        actor_id=leader_user_id,
    )
    return {
        "agent_run": completed_run,
        "analysis_memory": analysis_memory,
        "plan_memory": plan_memory,
        "plan": plan,
    }


def _approve_plan_v2(
    self: InMemoryRepository, leader_user_id: str, project_id: str, plan_id: str, comment: str
) -> dict[str, object] | None:
    plan = self.plans.get(plan_id)
    if plan is None or plan.project_id != project_id:
        return None
    if plan.generation_mode == "forced_risky" or (plan.planning_readiness is not None and not plan.planning_readiness.ready):
        raise ValueError("高风险草稿或资料不足计划不能直接批准，请补充材料后重新生成正式计划。")
    if not plan.structured_plan:
        raise ValueError("空计划不能批准，请先生成包含任务链的计划草稿。")
    approved_plan = plan.model_copy(update={"plan_status": "approved", "leader_feedback": comment, "approved_at": self._now()})
    self.plans[plan_id] = approved_plan

    dispatch_payload = _generate_dispatch_payload(self, project_id, approved_plan)
    dispatch_map = {
        int(item["task_index"]): item
        for item in dispatch_payload["tasks"]
        if isinstance(item, dict) and str(item.get("task_index", "")).strip()
    }

    generated_tasks: list[Task] = []
    previous_task_id: str | None = None
    for draft in approved_plan.structured_plan:
        dispatch_item = dispatch_map.get(draft.task_index, _build_fallback_dispatch_item(draft))
        submission_requirements = dispatch_item.get("submission_requirements", [])
        if not isinstance(submission_requirements, list):
            submission_requirements = []
        acceptance_standard = dispatch_item.get("acceptance_standard", [])
        if not isinstance(acceptance_standard, list):
            acceptance_standard = []
        handoff_details = [draft.handoff_requirements]
        if submission_requirements:
            handoff_details.append("提交要求：" + "；".join(str(item) for item in submission_requirements))
        if acceptance_standard:
            handoff_details.append("验收标准：" + "；".join(str(item) for item in acceptance_standard))

        task_id = f"exec-{project_id}-{approved_plan.version}-{draft.task_index}"
        task = Task(
            id=task_id,
            project_id=project_id,
            plan_id=approved_plan.id,
            task_index=draft.task_index,
            title=str(dispatch_item.get("title") or draft.title),
            task_type="计划任务",
            description=str(dispatch_item.get("goal") or draft.goal),
            status="assigned" if draft.task_index == 1 else "pending",
            tags=["计划执行"],
            owner_id=str(dispatch_item.get("assigned_user_id") or draft.assigned_user_id),
            reviewer_user_id=str(dispatch_item.get("reviewer_user_id") or draft.reviewer_user_id),
            review_status="草稿",
            next_action=str(dispatch_item.get("dispatch_message") or draft.handoff_requirements),
            initiator=leader_user_id,
            recommended_experts=[str(dispatch_item.get("assigned_user_id") or draft.assigned_user_id)],
            predecessor_task_id=previous_task_id,
            dependencies=[previous_task_id] if previous_task_id else [],
            dependency_ids=[previous_task_id] if previous_task_id else [],
            handoff_requirements=" / ".join(part for part in handoff_details if part),
            due_at=str(dispatch_item.get("ddl") or draft.ddl),
        )
        self.tasks[task.id] = task
        generated_tasks.append(task)
        previous_task_id = task.id
    WorkflowGateService(self).build_plan_workflow(project_id, approved_plan.id, generated_tasks)


    agent_run = self.agent_runs.get(approved_plan.generated_by_agent_run_id)
    draft_memory = self.memories.get(agent_run.plan_output_memory_id) if agent_run and agent_run.plan_output_memory_id else None
    if draft_memory is not None:
        plan_memory = draft_memory.model_copy(
            update={
                "memory_layer": "shared",
                "memory_type": "plan_final",
                "title": f"{approved_plan.plan_title or self.projects[project_id].name} v{approved_plan.version}",
                "summary": _plan_payload_to_summary(approved_plan),
                "source": f"Plan:{approved_plan.id}",
                "source_or_provenance": f"Plan:{approved_plan.id}",
                "confidence": "已确认",
                "review_status": "已确认",
                "tags": ["正式计划", "共享层"],
                "shared": True,
                "owner_user_id": leader_user_id,
                "visible_to_user_ids": [],
                "updated_at": self._now(),
            }
        )
    else:
        plan_memory = MemoryItem(
            id=f"m{len(self.memories) + 1}",
            project_id=project_id,
            memory_layer="shared",
            memory_type="plan_final",
            title=f"{approved_plan.plan_title or self.projects[project_id].name} v{approved_plan.version}",
            summary=_plan_payload_to_summary(approved_plan),
            source=f"Plan:{approved_plan.id}",
            source_or_provenance=f"Plan:{approved_plan.id}",
            confidence="已确认",
            review_status="已确认",
            tags=["正式计划", "共享层"],
            shared=True,
            owner_user_id=leader_user_id,
            visible_to_user_ids=[],
        )
    self.memories[plan_memory.id] = plan_memory
    for approval in list(self.approval_items.values()):
        if approval.object_type == "memory" and approval.object_id == plan_memory.id and approval.status == "pending":
            self.approval_items[approval.id] = approval.model_copy(
                update={
                    "status": "approved",
                    "resolved_by": leader_user_id,
                    "resolved_at": self._now(),
                    "resolution_comment": comment or "计划批准后自动进入共享层",
                }
            )

    self.add_audit_event(
        project_id=project_id,
        action="批准正式计划",
        object_type="plan",
        object_id=approved_plan.id,
        message=f"计划 v{approved_plan.version} 已进入共享层并发放任务。",
        actor_id=leader_user_id,
    )
    return {
        "plan": approved_plan,
        "tasks": generated_tasks,
        "plan_memory": plan_memory,
        "dispatch_batch_title": dispatch_payload["dispatch_batch_title"],
    }
