from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.domain import (
    AcceptanceDecisionInput,
    AssistantQueryInput,
    AgentIntakeInput,
    ApprovalDecisionInput,
    JoinRequestCreateInput,
    JoinRequestRejectInput,
    LLMConfigInput,
    MapView,
    MemoryCreate,
    MemoryUpdateInput,
    ProjectCreateInput,
    ProjectSourceTextInput,
    PlanRevisionInput,
    PlanningRunInput,
    SystemModeUpdate,
    TaskSubmitInput,
    TermCreateInput,
    TrustEventInput,
    WorkflowAdvanceInput,
)
from app.repository import InMemoryRepository
from app.services.ingest import extract_markdown_text, extract_pdf_text
from app.tms import recommend_experts, run_agent_intake


def create_app() -> FastAPI:
    app = FastAPI(title="研究团队 TMS 协作系统", version="0.2.0")
    repository = InMemoryRepository()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": "normal"}

    @app.get("/api/projects")
    def list_projects() -> dict[str, object]:
        return {"projects": repository.list_projects()}

    @app.get("/api/users")
    def list_users() -> dict[str, object]:
        return {"users": repository.list_users()}

    @app.get("/api/users/{user_id}/plaza")
    def get_plaza(user_id: str) -> dict[str, object]:
        user = repository.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        return {"current_user": user, "projects": repository.list_plaza_projects(user_id)}

    @app.post("/api/users/{user_id}/projects")
    def create_project(user_id: str, payload: ProjectCreateInput) -> object:
        user = repository.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        _require_database_globally_writable()
        return repository.create_project(user_id, payload)

    @app.post("/api/users/{user_id}/projects/{project_id}/project-sources/text")
    def create_project_source_from_text(user_id: str, project_id: str, payload: ProjectSourceTextInput) -> object:
        _require_user_project_access(user_id, project_id)
        _require_database_writable(project_id)
        return repository.create_project_source_from_text(user_id, project_id, payload)

    @app.post("/api/users/{user_id}/projects/{project_id}/project-sources/pdf")
    async def create_project_source_from_pdf(user_id: str, project_id: str, file: UploadFile = File(...)) -> object:
        _require_user_project_access(user_id, project_id)
        _require_database_writable(project_id)
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="仅支持 PDF 文件上传")
        file_bytes = await file.read()
        extracted_text = extract_pdf_text(file_bytes)
        return repository.create_project_source_from_pdf(user_id, project_id, file.filename, extracted_text)

    @app.post("/api/users/{user_id}/projects/{project_id}/project-sources/markdown")
    async def create_project_source_from_markdown(user_id: str, project_id: str, file: UploadFile = File(...)) -> object:
        _require_user_project_access(user_id, project_id)
        _require_database_writable(project_id)
        if not file.filename or not file.filename.lower().endswith(".md"):
            raise HTTPException(status_code=400, detail="仅支持 Markdown 文件上传")
        file_bytes = await file.read()
        markdown_text = extract_markdown_text(file_bytes)
        return repository.create_project_source_from_markdown(user_id, project_id, file.filename, markdown_text)

    @app.post("/api/users/{user_id}/projects/{project_id}/capability-submissions")
    async def create_capability_submission(
        user_id: str,
        project_id: str,
        raw_text: str = Form(...),
        proof_file: UploadFile | None = File(None),
    ) -> object:
        _require_user_project_access(user_id, project_id)
        _require_database_writable(project_id)
        proof_text = ""
        proof_file_name: str | None = None
        if proof_file is not None and proof_file.filename:
            if not proof_file.filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail="仅支持 PDF 证明材料上传")
            proof_bytes = await proof_file.read()
            proof_text = extract_pdf_text(proof_bytes)
            proof_file_name = proof_file.filename
        return repository.create_capability_submission(user_id, project_id, raw_text, proof_file_name, proof_text)

    @app.post("/api/users/{user_id}/projects/{project_id}/agent-runs")
    def run_planning_agent(user_id: str, project_id: str, payload: PlanningRunInput | None = None) -> object:
        _require_user_project_access(user_id, project_id)
        _require_database_writable(project_id)
        if not repository.is_project_leader(user_id, project_id):
            raise HTTPException(status_code=403, detail="只有组长可以运行 agent")
        return repository.run_planning_agent(user_id, project_id, force_generate=bool(payload.force_generate) if payload else False)

    @app.post("/api/users/{user_id}/projects/{project_id}/plans/{plan_id}/approve")
    def approve_plan(user_id: str, project_id: str, plan_id: str, payload: dict[str, str]) -> object:
        _require_user_project_access(user_id, project_id)
        _require_database_writable(project_id)
        if not repository.is_project_leader(user_id, project_id):
            raise HTTPException(status_code=403, detail="只有组长可以批准计划")
        try:
            result = repository.approve_plan(user_id, project_id, plan_id, payload.get("comment", ""))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=404, detail="计划不存在")
        return result

    @app.put("/api/users/{user_id}/projects/{project_id}/plans/{plan_id}")
    def revise_plan(user_id: str, project_id: str, plan_id: str, payload: PlanRevisionInput) -> object:
        _require_user_project_access(user_id, project_id)
        _require_database_writable(project_id)
        if not repository.is_project_leader(user_id, project_id):
            raise HTTPException(status_code=403, detail="只有组长可以修改计划")
        result = repository.revise_plan(user_id, project_id, plan_id, payload)
        if result is None:
            raise HTTPException(status_code=404, detail="计划不存在")
        return result

    @app.post("/api/users/{user_id}/projects/{project_id}/plans/{plan_id}/regenerate")
    def regenerate_plan(user_id: str, project_id: str, plan_id: str) -> object:
        _require_user_project_access(user_id, project_id)
        _require_database_writable(project_id)
        if not repository.is_project_leader(user_id, project_id):
            raise HTTPException(status_code=403, detail="只有组长可以退回重做计划")
        result = repository.regenerate_plan(user_id, project_id, plan_id)
        if result is None:
            raise HTTPException(status_code=404, detail="计划不存在")
        return result

    @app.post("/api/users/{user_id}/projects/{project_id}/tasks/{task_id}/submit")
    async def submit_task_result(
        user_id: str,
        project_id: str,
        task_id: str,
        request: Request,
        result_file: UploadFile | None = File(None),
        summary: str | None = Form(None),
        handoff_note: str | None = Form(None),
    ) -> object:
        _require_user_project_access(user_id, project_id)
        _require_database_writable(project_id)
        task = repository.get_task(task_id)
        if task is None or task.project_id != project_id:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task.owner_id != user_id:
            raise HTTPException(status_code=403, detail="只有任务负责人可以提交结果")
        payload: TaskSubmitInput
        result_file_name: str | None = None
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
            payload = TaskSubmitInput(**body)
        else:
            payload = TaskSubmitInput(summary=summary or "", handoff_note=handoff_note or "")
            if result_file is not None:
                if not result_file.filename or not result_file.filename.lower().endswith(".pdf"):
                    raise HTTPException(status_code=400, detail="仅支持 PDF 文件上传")
                result_file_name = result_file.filename
                await result_file.read()
        result = repository.submit_task_result(user_id, project_id, task_id, payload, result_file_name=result_file_name)
        if result is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        return result

    @app.post("/api/users/{user_id}/projects/{project_id}/tasks/{task_id}/acceptance/start")
    def start_acceptance(user_id: str, project_id: str, task_id: str) -> object:
        _require_user_project_access(user_id, project_id)
        _require_database_writable(project_id)
        task = repository.get_task(task_id)
        if task is None or task.project_id != project_id:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task.reviewer_user_id != user_id:
            raise HTTPException(status_code=403, detail="只有指定验收人可以开始验收")
        result = repository.start_acceptance(user_id, project_id, task_id)
        if result is None:
            raise HTTPException(status_code=404, detail="验收对象不存在")
        return result

    @app.post("/api/users/{user_id}/projects/{project_id}/tasks/{task_id}/acceptance/decide")
    def decide_acceptance(user_id: str, project_id: str, task_id: str, payload: AcceptanceDecisionInput) -> object:
        _require_user_project_access(user_id, project_id)
        _require_database_writable(project_id)
        task = repository.get_task(task_id)
        if task is None or task.project_id != project_id:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task.reviewer_user_id != user_id:
            raise HTTPException(status_code=403, detail="只有指定验收人可以提交验收结果")
        result = repository.decide_acceptance(user_id, project_id, task_id, payload)
        if result is None:
            raise HTTPException(status_code=404, detail="验收记录不存在")
        return result

    @app.post("/api/users/{user_id}/projects/{project_id}/assistant/query")
    def query_project_assistant(user_id: str, project_id: str, payload: AssistantQueryInput) -> object:
        _require_user_project_access(user_id, project_id)
        return repository.answer_project_question(user_id, project_id, payload.query)

    @app.get("/api/users/{user_id}/projects")
    def list_user_projects(user_id: str) -> dict[str, object]:
        user = repository.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        return {"current_user": user, "projects": repository.list_user_projects(user_id) or []}

    @app.post("/api/users/{user_id}/projects/{project_id}/join-requests")
    def create_join_request(user_id: str, project_id: str, payload: JoinRequestCreateInput) -> object:
        if repository.get_user(user_id) is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        if repository.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        if repository.user_can_access_project(user_id, project_id):
            raise HTTPException(status_code=409, detail="当前用户已在项目中")
        _require_database_writable(project_id)
        return repository.create_join_request(user_id, project_id, payload)

    @app.post("/api/users/{user_id}/projects/{project_id}/join-requests/{request_id}/approve")
    def approve_join_request(user_id: str, project_id: str, request_id: str) -> object:
        if not repository.is_project_leader(user_id, project_id):
            raise HTTPException(status_code=403, detail="只有组长可以处理入组申请")
        _require_database_writable(project_id)
        request = repository.approve_join_request(user_id, project_id, request_id)
        if request is None:
            raise HTTPException(status_code=404, detail="入组申请不存在")
        return request

    @app.post("/api/users/{user_id}/projects/{project_id}/join-requests/{request_id}/reject")
    def reject_join_request(user_id: str, project_id: str, request_id: str, payload: JoinRequestRejectInput) -> object:
        if not repository.is_project_leader(user_id, project_id):
            raise HTTPException(status_code=403, detail="只有组长可以处理入组申请")
        _require_database_writable(project_id)
        request = repository.reject_join_request(user_id, project_id, request_id, payload)
        if request is None:
            raise HTTPException(status_code=404, detail="入组申请不存在")
        return request

    @app.get("/api/projects/{project_id}/workspace")
    def get_workspace(project_id: str) -> dict[str, object]:
        project = repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        return _workspace_payload(project_id)

    @app.get("/api/users/{user_id}/projects/{project_id}/workspace")
    def get_user_workspace(user_id: str, project_id: str) -> dict[str, object]:
        _require_user_project_access(user_id, project_id)
        return _workspace_payload(project_id, user_id)

    @app.post("/api/projects/{project_id}/tasks/{task_id}/recommendations")
    def get_recommendations(project_id: str, task_id: str) -> object:
        project = repository.get_project(project_id)
        task = repository.get_task(task_id)
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        if task is None or task.project_id != project_id:
            raise HTTPException(status_code=404, detail="任务不存在")
        return recommend_experts(project, task, repository.list_project_actors(project_id))

    @app.put("/api/projects/{project_id}/llm-config")
    def save_llm_config(project_id: str, config: LLMConfigInput) -> object:
        if repository.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        return repository.save_llm_config(project_id, config)

    @app.get("/api/users/{user_id}/projects/{project_id}/llm-diagnostics")
    def get_project_llm_diagnostics(user_id: str, project_id: str) -> object:
        _require_user_project_access(user_id, project_id)
        return repository.get_project_llm_diagnostics(project_id)

    @app.post("/api/projects/{project_id}/memories")
    def create_memory(project_id: str, payload: MemoryCreate) -> object:
        if repository.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        _require_database_writable(project_id)
        return repository.create_memory(project_id, payload)

    @app.post("/api/projects/{project_id}/memories/{memory_id}/approve")
    def approve_memory(project_id: str, memory_id: str) -> object:
        raise HTTPException(status_code=410, detail="请使用组长审批队列接口批准共享记忆")

    @app.put("/api/users/{user_id}/projects/{project_id}/memories/{memory_id}")
    def update_memory(user_id: str, project_id: str, memory_id: str, payload: MemoryUpdateInput) -> object:
        _require_user_project_access(user_id, project_id)
        _require_database_writable(project_id)
        memory = repository.update_memory(project_id, memory_id, payload, user_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="记忆不存在")
        return memory

    @app.post("/api/projects/{project_id}/handover")
    def generate_handover(project_id: str) -> object:
        _require_database_writable(project_id)
        bundle = repository.generate_handover(project_id)
        if bundle is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        return bundle

    @app.post("/api/users/{user_id}/projects/{project_id}/workflows/{workflow_id}/advance")
    def advance_workflow(user_id: str, project_id: str, workflow_id: str, payload: WorkflowAdvanceInput) -> object:
        _require_user_project_access(user_id, project_id)
        try:
            workflow = repository.advance_workflow(user_id, project_id, workflow_id, payload.note)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if workflow is None:
            raise HTTPException(status_code=404, detail="闭环流程不存在")
        return workflow

    @app.put("/api/projects/{project_id}/system-mode")
    def set_system_mode(project_id: str, update: SystemModeUpdate) -> object:
        if repository.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        return repository.set_system_state(project_id, update)

    @app.get("/api/projects/{project_id}/audit-log")
    def list_audit_log(project_id: str) -> dict[str, object]:
        if repository.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        return {"events": repository.list_audit_events(project_id)}

    @app.get("/api/users/{user_id}/projects/{project_id}/terms")
    def list_terms(user_id: str, project_id: str, q: str = "", include_team: bool = False) -> dict[str, object]:
        _require_user_project_access(user_id, project_id)
        return {"entries": repository.list_terms(project_id, q, include_team=include_team)}

    @app.post("/api/users/{user_id}/projects/{project_id}/terms")
    def create_term(user_id: str, project_id: str, payload: TermCreateInput) -> object:
        _require_user_project_access(user_id, project_id)
        _require_database_writable(project_id)
        return repository.create_term(project_id, user_id, payload)

    @app.get("/api/users/{user_id}/projects/{project_id}/approvals")
    def list_approvals(user_id: str, project_id: str) -> dict[str, object]:
        _require_user_project_access(user_id, project_id)
        return {"items": repository.list_approvals(project_id, user_id=user_id)}

    @app.post("/api/users/{user_id}/projects/{project_id}/approvals/{approval_id}/decide")
    def decide_approval(user_id: str, project_id: str, approval_id: str, payload: ApprovalDecisionInput) -> object:
        _require_user_project_access(user_id, project_id)
        _require_database_writable(project_id)
        try:
            item = repository.decide_approval(user_id, project_id, approval_id, payload)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if item is None:
            raise HTTPException(status_code=404, detail="审批项不存在")
        return item

    @app.post("/api/users/{user_id}/projects/{project_id}/agent-intake")
    def agent_intake(user_id: str, project_id: str, payload: AgentIntakeInput) -> object:
        _require_user_project_access(user_id, project_id)
        _require_llm_available(project_id)
        result = run_agent_intake(payload, created_by=user_id)
        return repository.save_agent_intake_result(result)

    @app.get("/api/users/{user_id}/projects/{project_id}/expertise-map")
    def get_expertise_map(user_id: str, project_id: str, view: MapView = "person") -> object:
        _require_user_project_access(user_id, project_id)
        return repository.build_expertise_map(project_id, view)

    @app.post("/api/users/{user_id}/projects/{project_id}/trust-events")
    def record_trust_event(user_id: str, project_id: str, payload: TrustEventInput) -> object:
        _require_user_project_access(user_id, project_id)
        _require_database_writable(project_id)
        if not repository.is_project_leader(user_id, project_id):
            raise HTTPException(status_code=403, detail="只有组长可以记录重大 trust 事件")
        return repository.record_trust_event(project_id, payload, user_id)

    @app.get("/api/users/{user_id}/projects/{project_id}/search")
    def search_project(user_id: str, project_id: str, q: str) -> object:
        _require_user_project_access(user_id, project_id)
        return repository.search_project(project_id, q)

    def _workspace_payload(project_id: str, user_id: str | None = None) -> dict[str, object]:
        payload: dict[str, object] = {
            "project": repository.get_project(project_id),
            "actors": repository.list_project_actors(project_id),
            "expert_profiles": repository.list_expert_profiles(project_id),
            "expert_relations": repository.list_expert_relations(project_id),
            "tasks": repository.list_tasks(project_id),
            "memories": repository.list_memories(project_id, user_id),
            "decisions": repository.list_decisions(project_id),
            "evidence": repository.list_evidence(project_id),
            "workflows": repository.list_workflows(project_id),
            "system_state": repository.get_system_state(project_id),
            "terms": repository.list_terms(project_id, include_team=False),
            "approvals": repository.list_approvals(project_id, user_id=user_id) if user_id is not None else repository.list_approvals(project_id),
            "plans": repository.list_plans(project_id),
            "handover_bundles": repository.list_handover_bundles(project_id),
            "llm_diagnostics": repository.get_project_llm_diagnostics(project_id),
        }
        if user_id is not None:
            payload["current_user"] = repository.get_user(user_id)
            payload["is_project_leader"] = repository.is_project_leader(user_id, project_id)
            payload["current_user_project_role"] = next(
                (
                    member.role
                    for member in repository.project_members.values()
                    if member.project_id == project_id and member.user_id == user_id and member.membership_status == "active"
                ),
                None,
            )
        return payload

    def _require_user_project_access(user_id: str, project_id: str) -> None:
        if repository.get_user(user_id) is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        if repository.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        if not repository.user_can_access_project(user_id, project_id):
            raise HTTPException(status_code=403, detail="无权访问该项目")

    def _require_database_writable(project_id: str) -> None:
        state = repository.get_system_state(project_id)
        if not state.database_writable or state.mode == "readonly_protection":
            raise HTTPException(status_code=409, detail="系统当前处于只读保护模式，禁止写入和审批操作")

    def _require_database_globally_writable() -> None:
        if any(not state.database_writable or state.mode == "readonly_protection" for state in repository.system_states.values()):
            raise HTTPException(status_code=409, detail="系统当前处于只读保护模式，禁止写入和审批操作")

    def _require_llm_available(project_id: str) -> None:
        state = repository.get_system_state(project_id)
        if not state.llm_available or state.mode == "manual_collaboration":
            raise HTTPException(status_code=409, detail="系统当前处于人工协作模式，Agent Intake 已暂停，请改用人工录入")

    return app


app = create_app()
