from __future__ import annotations

from app.domain import ExpertProfileRecord, PlanTaskDraft


def _profile_text(profile: ExpertProfileRecord) -> str:
    parts: list[str] = []
    for claim in profile.structured_capabilities:
        parts.extend(
            [
                claim.domain,
                claim.method,
                claim.tool,
                claim.boundaries,
                " ".join(claim.supported_roles),
            ]
        )
    return " ".join(part for part in parts if part).lower()


def _profile_supports_review(profile: ExpertProfileRecord) -> bool:
    return any("审阅" in role for claim in profile.structured_capabilities for role in claim.supported_roles)


def _score_profile(profile: ExpertProfileRecord, keywords: list[str], preferred_role: str | None = None) -> float:
    text = _profile_text(profile)
    score = profile.current_confidence
    for keyword in keywords:
        if keyword.lower() in text:
            score += 2.0
    if preferred_role and any(preferred_role in role for claim in profile.structured_capabilities for role in claim.supported_roles):
        score += 1.0
    return score


def _pick_best_profile(
    active_profiles: list[ExpertProfileRecord],
    keywords: list[str],
    preferred_role: str | None = None,
    excluded_user_ids: set[str] | None = None,
) -> ExpertProfileRecord | None:
    excluded = excluded_user_ids or set()
    candidates = [profile for profile in active_profiles if profile.user_id not in excluded]
    if not candidates:
        return None
    return max(candidates, key=lambda profile: _score_profile(profile, keywords, preferred_role))


def _pick_reviewer(
    active_profiles: list[ExpertProfileRecord],
    reviewer: str,
    assigned_user_id: str,
    preferred_keywords: list[str],
) -> str:
    candidates = [profile for profile in active_profiles if profile.user_id != assigned_user_id and _profile_supports_review(profile)]
    if not candidates:
        return reviewer
    selected = max(candidates, key=lambda profile: _score_profile(profile, preferred_keywords, "审阅"))
    return selected.user_id


def build_plan_tasks(project_id: str, active_profiles: list[ExpertProfileRecord], reviewer: str) -> list[PlanTaskDraft]:
    del project_id

    governance = _pick_best_profile(
        active_profiles,
        ["项目治理", "计划编排", "交接", "里程碑", "内容管理", "知识管理", "审批", "门控"],
        "执行",
    )
    engineering = _pick_best_profile(
        active_profiles,
        ["系统开发", "软件开发", "前后端", "接口联调", "实现", "架构", "版本控制", "协作", "python", "代码维护", "落地实现"],
        "执行",
    )
    testing = _pick_best_profile(
        active_profiles,
        ["软件测试", "测试设计", "自动化验收", "验收", "质量", "风险管理", "系统风险", "安全压力测试", "代码优化", "功能测试"],
        "执行",
    )

    fallback_user = active_profiles[0].user_id if active_profiles else "u2"
    governance_user = governance.user_id if governance else fallback_user
    engineering_user = engineering.user_id if engineering else fallback_user
    testing_user = testing.user_id if testing else governance_user

    tasks = [
        PlanTaskDraft(
            task_index=1,
            title="固化项目目标与约束",
            goal="基于共享层正式资料澄清项目目标、范围、时间约束和验收边界。",
            assigned_user_id=governance_user,
            reviewer_user_id=_pick_reviewer(active_profiles, reviewer, governance_user, ["项目治理", "验收", "测试"]) or reviewer,
            handoff_requirements="提交目标、范围、约束和验收标准摘要，并标明来源记忆。",
            ddl="T+2天",
        ),
        PlanTaskDraft(
            task_index=2,
            title="完成系统方案与实现拆解",
            goal="把项目目标转成可执行的系统方案、模块拆解和实现路径。",
            assigned_user_id=engineering_user,
            reviewer_user_id=_pick_reviewer(active_profiles, reviewer, engineering_user, ["系统开发", "软件开发", "接口联调", "版本控制", "项目治理"]) or reviewer,
            handoff_requirements="提交系统方案、模块划分和实现说明，并对接上一步的目标约束。",
            ddl="T+4天",
            predecessor_task_id="task-1",
            dependency_ids=["task-1"],
        ),
        PlanTaskDraft(
            task_index=3,
            title="制定测试与验收方案",
            goal="围绕实现方案制定测试用例、验收标准和回流机制。",
            assigned_user_id=testing_user,
            reviewer_user_id=_pick_reviewer(active_profiles, reviewer, testing_user, ["软件测试", "风险管理", "代码优化", "项目治理", "审阅"]) or reviewer,
            handoff_requirements="提交测试设计、验收清单和驳回条件，并绑定对应交付物。",
            ddl="T+5天",
            predecessor_task_id="task-2",
            dependency_ids=["task-2"],
        ),
        PlanTaskDraft(
            task_index=4,
            title="汇总阶段交接与执行门控",
            goal="汇总前三步结果，形成阶段执行建议、交接要求和共享层入库门槛。",
            assigned_user_id=governance_user,
            reviewer_user_id=_pick_reviewer(active_profiles, reviewer, governance_user, ["项目治理", "测试", "系统开发", "软件开发"]) or reviewer,
            handoff_requirements="生成阶段计划、交接说明和最终共享层门控要求，验收通过前不得入共享层。",
            ddl="T+7天",
            predecessor_task_id="task-3",
            dependency_ids=["task-3"],
        ),
    ]

    deduped_tasks: list[PlanTaskDraft] = []
    for task in tasks:
        if deduped_tasks and deduped_tasks[-1].title == task.title:
            continue
        deduped_tasks.append(task)
    return deduped_tasks
