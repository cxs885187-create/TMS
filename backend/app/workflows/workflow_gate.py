from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain import AcceptanceRecord, MemoryCreate, Task, TMSWorkflow, WorkflowStep
from app.workflows.governance import ensure_project_leader

if TYPE_CHECKING:
    from app.repository import InMemoryRepository


class WorkflowGateService:
    def __init__(self, repository: InMemoryRepository) -> None:
        self.repository = repository

    def build_plan_workflow(self, project_id: str, plan_id: str, tasks: list[Task]) -> TMSWorkflow:
        if not tasks:
            workflow = TMSWorkflow(
                id=f"wf-{plan_id}",
                project_id=project_id,
                loop_type="任务执行闭环",
                title="任务执行闭环",
                description="上游提交、下游验收、组长最终确认的线性闭环。",
                related_object_id=plan_id,
                steps=self._steps_for_status("readonly"),
                current_state="draft",
                gate_status="readonly",
                current_task_id=None,
                state_message="暂无任务链。",
                advance_action_label="组长确认推进",
                allowed_advance_user_ids=[],
            )
            self.repository.workflows[workflow.id] = workflow
            return workflow

        created: list[TMSWorkflow] = []
        for index, task in enumerate(tasks):
            active = index == 0
            gate_status = "waiting_upstream_submission" if active else "readonly"
            workflow = TMSWorkflow(
                id=f"wf-{plan_id}-{task.task_index or index + 1}",
                project_id=project_id,
                loop_type="任务执行闭环",
                title=f"步骤 {task.task_index or index + 1}：{task.title}",
                description="该闭环对应正式计划中的一个线性步骤：负责人提交、验收人确认、组长最终确认。",
                related_object_id=plan_id,
                steps=self._steps_for_status(gate_status),
                current_state="in_progress" if active else "draft",
                gate_status=gate_status,
                current_task_id=task.id,
                state_message=(
                    f"等待 {task.title} 的负责人提交结果。"
                    if active
                    else f"等待上一步完成组长确认后解锁“{task.title}”。"
                ),
                advance_action_label="组长确认推进",
                allowed_advance_user_ids=[],
            )
            self.repository.workflows[workflow.id] = workflow
            created.append(workflow)
        return created[0]

    def mark_submission(self, project_id: str, submitted_task: Task) -> None:
        workflow = self._find_workflow_for_task(project_id, submitted_task.id) or self._find_workflow_for_plan(project_id, submitted_task.plan_id)
        if workflow is None:
            return
        message = f"{submitted_task.title} 已提交，等待下游验收。"
        self._save_workflow(
            workflow,
            gate_status="waiting_downstream_acceptance",
            current_task_id=submitted_task.id,
            state_message=message,
            allowed_advance_user_ids=[],
        )

    def mark_acceptance_started(self, project_id: str, current_task: Task, previous_task: Task) -> None:
        workflow = self._find_workflow_for_task(project_id, previous_task.id) or self._find_workflow_for_plan(project_id, current_task.plan_id)
        if workflow is None:
            return
        self._save_workflow(
            workflow,
            gate_status="waiting_downstream_acceptance",
            current_task_id=previous_task.id,
            state_message=f"{previous_task.title} 正在由下游成员验收。",
            allowed_advance_user_ids=[],
        )

    def mark_reviewer_decision(
        self,
        project_id: str,
        current_task: Task,
        previous_task: Task,
        acceptance: AcceptanceRecord,
    ) -> None:
        workflow = self._find_workflow_for_task(project_id, previous_task.id) or self._find_workflow_for_plan(project_id, current_task.plan_id)
        if workflow is None:
            return
        if acceptance.decision == "accepted":
            leader_ids = self.repository.get_project_leader_ids(project_id)
            self._save_workflow(
                workflow,
                gate_status="waiting_leader_confirmation",
                current_task_id=previous_task.id,
                state_message=f"{previous_task.title} 已通过下游验收，等待组长最终确认。",
                allowed_advance_user_ids=leader_ids,
            )
            return
        self._save_workflow(
            workflow,
            gate_status="rework_required",
            current_task_id=previous_task.id,
            state_message=f"{previous_task.title} 已被驳回，等待上游修改后重新提交。",
            allowed_advance_user_ids=[],
        )

    def mark_terminal_reviewer_decision(
        self,
        project_id: str,
        terminal_task: Task,
        acceptance: AcceptanceRecord,
    ) -> None:
        workflow = self._find_workflow_for_task(project_id, terminal_task.id) or self._find_workflow_for_plan(project_id, terminal_task.plan_id)
        if workflow is None:
            return
        leader_ids = self.repository.get_project_leader_ids(project_id)
        self._save_workflow(
            workflow,
            gate_status="waiting_leader_confirmation",
            current_task_id=terminal_task.id,
            state_message=f"{terminal_task.title} 已通过验收，等待组长最终确认收束闭环。",
            allowed_advance_user_ids=leader_ids,
        )

    def mark_terminal_reviewer_rejection(
        self,
        project_id: str,
        terminal_task: Task,
        acceptance: AcceptanceRecord,
    ) -> None:
        workflow = self._find_workflow_for_task(project_id, terminal_task.id) or self._find_workflow_for_plan(project_id, terminal_task.plan_id)
        if workflow is None:
            return
        self._save_workflow(
            workflow,
            gate_status="rework_required",
            current_task_id=terminal_task.id,
            state_message=f"{terminal_task.title} 已被驳回，等待重新提交。",
            allowed_advance_user_ids=[],
        )

    def leader_confirm(self, leader_user_id: str, project_id: str, workflow_id: str, note: str = "") -> TMSWorkflow | None:
        workflow = self.repository.workflows.get(workflow_id)
        if workflow is None or workflow.project_id != project_id:
            return None
        ensure_project_leader(self.repository, leader_user_id, project_id, "进行最终推进确认")
        if workflow.gate_status != "waiting_leader_confirmation" or not workflow.current_task_id:
            raise ValueError("当前闭环不处于可由组长最终确认的状态")

        current_task = self.repository.tasks.get(workflow.current_task_id)
        if current_task is None:
            raise ValueError("当前闭环缺少待确认任务")
        acceptance = self._latest_acceptance(project_id, current_task.id)
        if acceptance is None or acceptance.decision != "accepted":
            raise ValueError("当前没有可供组长确认的验收通过记录")

        self.repository.acceptance_records[acceptance.id] = acceptance.model_copy(
            update={
                "leader_decision": "approved",
                "leader_comment": note.strip() or "组长确认推进",
                "leader_confirmed_by": leader_user_id,
                "leader_confirmed_at": self.repository._now(),
            }
        )
        completed_task = current_task.model_copy(
            update={"status": "completed", "workflow_gate_status": "completed", "leader_confirmation_status": "approved"}
        )
        self.repository.tasks[current_task.id] = completed_task
        completed_workflow = self._save_workflow(
            workflow,
            gate_status="completed",
            current_task_id=current_task.id,
            state_message=f"{current_task.title} 已完成最终确认，当前步骤闭环已完成。",
            allowed_advance_user_ids=[],
        )
        next_task = self._find_next_task(completed_task)
        self._create_recalculation_memories(project_id, leader_user_id, completed_task, next_task or completed_task, acceptance.id)
        if next_task is None:
            return completed_workflow

        unlocked_next = next_task.model_copy(
            update={"status": "assigned", "workflow_gate_status": "waiting_upstream_submission", "leader_confirmation_status": "not_required"}
        )
        self.repository.tasks[next_task.id] = unlocked_next
        next_workflow = self._find_workflow_for_task(project_id, next_task.id)
        if next_workflow is None:
            return completed_workflow
        return self._save_workflow(
            next_workflow,
            gate_status="waiting_upstream_submission",
            current_task_id=next_task.id,
            state_message=f"{next_task.title} 已解锁，等待负责人提交结果。",
            allowed_advance_user_ids=[],
        )

    def _find_workflow_for_task(self, project_id: str, task_id: str | None) -> TMSWorkflow | None:
        if not task_id:
            return None
        return next(
            (
                workflow
                for workflow in self.repository.workflows.values()
                if workflow.project_id == project_id
                and workflow.current_task_id == task_id
                and workflow.loop_type == "任务执行闭环"
            ),
            None,
        )

    def _find_workflow_for_plan(self, project_id: str, plan_id: str | None) -> TMSWorkflow | None:
        if not plan_id:
            return None
        return next(
            (
                workflow
                for workflow in self.repository.workflows.values()
                if workflow.project_id == project_id and workflow.related_object_id == plan_id and workflow.loop_type == "任务执行闭环"
            ),
            None,
        )

    def _find_next_task(self, task: Task) -> Task | None:
        return next(
            (
                item
                for item in self.repository.tasks.values()
                if item.project_id == task.project_id and item.predecessor_task_id == task.id
            ),
            None,
        )

    def _latest_acceptance(self, project_id: str, task_id: str) -> AcceptanceRecord | None:
        return next(
            (
                record
                for record in reversed(list(self.repository.acceptance_records.values()))
                if record.project_id == project_id and record.task_id == task_id
            ),
            None,
        )

    def _steps_for_status(self, gate_status: str) -> list[WorkflowStep]:
        status_map = {
            "waiting_upstream_submission": ["进行中", "待开始", "待开始"],
            "waiting_downstream_acceptance": ["已完成", "进行中", "待开始"],
            "waiting_leader_confirmation": ["已完成", "已完成", "进行中"],
            "completed": ["已完成", "已完成", "已完成"],
            "rework_required": ["受阻", "待开始", "待开始"],
            "readonly": ["待开始", "待开始", "待开始"],
        }
        statuses = status_map.get(gate_status, status_map["readonly"])
        return [
            WorkflowStep(id="step-1", title="上游提交成果", status=statuses[0], required_output="提交结果与交接说明"),
            WorkflowStep(id="step-2", title="下游验收确认", status=statuses[1], required_output="完成验收结论"),
            WorkflowStep(id="step-3", title="组长最终确认", status=statuses[2], required_output="确认推进或驳回"),
        ]

    def _save_workflow(
        self,
        workflow: TMSWorkflow,
        gate_status: str,
        current_task_id: str | None,
        state_message: str,
        allowed_advance_user_ids: list[str],
    ) -> TMSWorkflow:
        updated = workflow.model_copy(
            update={
                "gate_status": gate_status,
                "current_task_id": current_task_id,
                "state_message": state_message,
                "allowed_advance_user_ids": allowed_advance_user_ids,
                "steps": self._steps_for_status(gate_status),
                "current_state": "approved" if gate_status == "completed" else "under_review",
            }
        )
        self.repository.workflows[workflow.id] = updated
        return updated

    def _create_recalculation_memories(
        self,
        project_id: str,
        created_by: str,
        previous_task: Task,
        current_task: Task,
        acceptance_id: str,
    ) -> None:
        profile = next((item for item in self.repository.list_expert_profiles(project_id) if item.user_id == (previous_task.owner_id or "")), None)
        if profile is not None:
            new_confidence = round(profile.current_confidence + 0.05, 3)
            confidence_memory = self.repository.create_memory(
                project_id,
                MemoryCreate(
                    memory_type="capability_score",
                    title=f"{profile.user_id} 本轮置信度更新提案",
                    summary=f"组长确认后建议将置信度从 {profile.current_confidence:.2f} 更新为 {new_confidence:.2f}",
                    source=f"Acceptance:{acceptance_id}",
                    confidence="待审核",
                    tags=["回算提案", "置信度"],
                ),
                created_by=created_by,
            )
            self.repository.pending_confidence_updates[confidence_memory.id] = {
                "profile_id": profile.id,
                "new_confidence": new_confidence,
            }
        status_memory = self.repository.create_memory(
            project_id,
            MemoryCreate(
                memory_type="project_status_snapshot",
                title=f"{project_id} 本轮项目状态提案",
                summary=f"任务“{previous_task.title}”已完成最终确认，当前任务“{current_task.title}”已正式解锁。",
                source=f"Acceptance:{acceptance_id}",
                confidence="待审核",
                tags=["回算提案", "项目状态"],
            ),
            created_by=created_by,
        )
        self.repository.pending_status_updates[status_memory.id] = {"task_id": previous_task.id}
        network_memory = self.repository.create_memory(
            project_id,
            MemoryCreate(
                memory_type="expert_network_snapshot",
                title=f"{project_id} 本轮专家网络提案",
                summary=f"建议确认 {previous_task.owner_id} -> {current_task.reviewer_user_id or created_by} 的协作关系。",
                source=f"Acceptance:{acceptance_id}",
                confidence="待审核",
                tags=["回算提案", "专家网络"],
            ),
            created_by=created_by,
        )
        relation = next(
            (
                item
                for item in self.repository.list_expert_relations(project_id)
                if item.from_user_id == (previous_task.owner_id or "") and item.to_user_id == (current_task.reviewer_user_id or created_by)
            ),
            None,
        )
        if relation is not None:
            self.repository.pending_relation_updates[network_memory.id] = {
                "relation_id": relation.id,
                "new_weight": round(relation.weight + 0.05, 3),
            }
