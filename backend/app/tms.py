from __future__ import annotations

import math

from app.domain import (
    Actor,
    AgentIntakeInput,
    AgentIntakeResult,
    IntakeReadiness,
    Project,
    RecommendationCandidate,
    RecommendationResult,
    StructuredCandidate,
    Task,
    VectorPayload,
)


VERIFIED_STATUSES = {"已验证", "同行确认", "主管确认", "系统验证增强"}
SUPPORTED_OBJECT_TYPES = {"任务", "文献记忆", "实验记录", "讨论记忆", "决策记录", "交接包", "专家声明", "术语条目"}


def recommend_experts(project: Project, task: Task, actors: list[Actor]) -> RecommendationResult:
    scored = [_score_actor(actor, task) for actor in actors]
    candidates = sorted((candidate for candidate in scored if candidate.score > 0), key=lambda candidate: candidate.score, reverse=True)

    human_candidates = [candidate for candidate in candidates if candidate.actor_type == "human"]
    ai_candidates = [candidate for candidate in candidates if candidate.actor_type == "ai"]
    has_enough_trust = any(_has_relevant_trust(actor, task.tags) for actor in actors)

    if not has_enough_trust:
        primary_expert = None
        if task.owner_id or task.recommended_experts:
            primary_expert = human_candidates[0] if human_candidates else None
        return RecommendationResult(
            mode="low_trust_data",
            primary_expert=primary_expert,
            secondary_collaborators=human_candidates[:3],
            reviewer_candidates=human_candidates[:2],
            ai_assistants=ai_candidates[:2],
            candidates=candidates,
            message=f"项目“{project.name}”当前历史数据不足，推荐基于声明专长、项目标签和角色适配。",
        )

    primary_expert = human_candidates[0] if human_candidates else None
    secondary = human_candidates[1:3] if len(human_candidates) > 1 else []
    reviewers = [candidate for candidate in human_candidates if any("审阅" in reason for reason in candidate.reasons)][:2]
    return RecommendationResult(
        mode="normal",
        primary_expert=primary_expert,
        secondary_collaborators=secondary,
        reviewer_candidates=reviewers,
        ai_assistants=ai_candidates[:2],
        candidates=candidates,
        message=f"已根据项目“{project.name}”的任务标签、验证专长、项目上下文与历史信任生成推荐。",
    )


def run_agent_intake(input_data: AgentIntakeInput, created_by: str, embedding_model: str = "text-embedding-3-small") -> AgentIntakeResult:
    object_type = input_data.object_type if input_data.object_type in SUPPORTED_OBJECT_TYPES else "讨论记忆"
    raw_input = input_data.raw_input.strip()
    source_refs = _extract_source_refs(raw_input)
    domain_tags = _extract_tags(
        raw_input,
        ["肿瘤免疫", "单细胞分析", "空间转录组", "统计审阅", "平台比较", "group behavior", "group mind", "social psychology"],
    )
    method_tags = _extract_tags(raw_input, ["Seurat", "流式分析", "复现实验", "批次校正", "方法检查", "theory", "analysis"])
    tool_tags = _extract_tags(raw_input, ["R", "FlowJo", "LLM", "Zotero", "pdf", "markdown"])
    title = raw_input[:24] if raw_input else f"{object_type} 草稿"
    quality_hints: list[str] = []
    missing_required_fields: list[str] = []
    summary = _build_intake_summary(raw_input)
    supplement_materials: list[dict[str, str | None]] = []

    if not source_refs:
        missing_required_fields.append("source_refs")
        quality_hints.append("缺少明确来源，当前只能作为待审核草稿，不能直接进入共享记忆。")
        supplement_materials.append(
            {
                "item_key": "source_refs",
                "label": "来源说明",
                "why_needed": "没有来源时，系统无法把这条内容作为正式项目事实引用。",
                "recommended_action": "补充来源、会议纪要、文档名或文件引用。",
                "material_id": None,
            }
        )
    if not domain_tags and not method_tags:
        quality_hints.append("缺少足够的项目上下文标签，建议补充任务目标、范围或方法线索。")
        supplement_materials.append(
            {
                "item_key": "project_context",
                "label": "项目上下文标签",
                "why_needed": "缺少目标、范围或方法线索时，系统无法稳定判断这条内容属于哪类项目事实。",
                "recommended_action": "补充任务目标、范围边界、方法名称或上下游责任描述。",
                "material_id": None,
            }
        )
    if "正式结论" in raw_input and "限制" not in raw_input and "局限" not in raw_input:
        quality_hints.append("建议补充限制条件，避免 AI 总结遗漏边界。")
        supplement_materials.append(
            {
                "item_key": "limitations",
                "label": "限制条件",
                "why_needed": "正式结论若没有限制条件，容易被误当作已确认事实。",
                "recommended_action": "补充限制、风险或不确定性说明。",
                "material_id": None,
            }
        )

    if not raw_input:
        readiness = IntakeReadiness(
            ready=False,
            status="blocked",
            message="智能录入失败：当前没有可分析的输入内容。",
            risk_summary="输入为空，无法生成结构化草稿。",
            risk_items=["缺少原始输入内容"],
            supplement_materials=[
                {
                    "item_key": "raw_input",
                    "label": "原始输入内容",
                    "why_needed": "没有输入文本时，系统无法进行任何结构化抽取。",
                    "recommended_action": "先粘贴自然语言内容后再执行智能录入。",
                    "material_id": None,
                }
            ],
            force_execute_allowed=False,
            force_executed=False,
        )
    elif missing_required_fields or len(supplement_materials) > 0:
        force_allowed = True
        forced = bool(input_data.force_execute and force_allowed)
        readiness = IntakeReadiness(
            ready=False,
            status="risky_but_ingestable",
            message="当前材料不足，建议先补充来源或上下文；如你确认要保留，也可强制入审核层。",
            risk_summary="当前智能录入存在信息缺口，强制执行后只能进入审核层，不能直接作为共享记忆。",
            risk_items=[*quality_hints] or ["当前信息存在缺口。"],
            supplement_materials=supplement_materials,
            force_execute_allowed=force_allowed,
            force_executed=forced,
        )
    else:
        readiness = IntakeReadiness(
            ready=True,
            status="ready",
            message="当前输入已满足智能录入的基本要求。",
            risk_summary="当前可进入审核层。",
            risk_items=[],
            supplement_materials=[],
            force_execute_allowed=False,
            force_executed=False,
        )

    structured = StructuredCandidate(
        object_type=object_type,
        project_id=input_data.project_id,
        title=title,
        summary=summary,
        domain_tags=domain_tags,
        method_tags=method_tags,
        tool_tags=tool_tags,
        source_refs=source_refs,
        missing_required_fields=missing_required_fields,
        review_required=True,
        suggested_next_action="已强制进入审核层，请补齐缺失材料后再申请共享。" if readiness.force_executed else "进入模板校验并提交人工确认。",
        status="待审阅" if readiness.force_executed else ("草稿" if missing_required_fields else "待审阅"),
    )

    vector_payload = VectorPayload(
        text=raw_input,
        chunk_id=f"chunk-{abs(hash((input_data.project_id, raw_input))) % 100000}",
        object_type=object_type,
        object_id=f"candidate-{abs(hash(raw_input)) % 100000}",
        project_id=input_data.project_id,
        tags=[*domain_tags, *method_tags, *tool_tags],
        created_by=created_by,
        visibility_scope="project",
        embedding_model=embedding_model,
    )
    return AgentIntakeResult(
        structured_candidate=structured,
        vector_payloads=[vector_payload],
        readiness=readiness,
        quality_hints=quality_hints,
        raw_input=raw_input,
        prompt_version="tms-agent-intake-v1",
        model_config_id=f"{input_data.project_id}-active-model",
        created_by=created_by,
    )


def _score_actor(actor: Actor, task: Task) -> RecommendationCandidate:
    reasons: list[str] = []
    score = 0.0
    factor_breakdown = {"domain_match": 0.0, "verification": 0.0, "trust": 0.0, "role_fit": 0.0, "ai_assist": 0.0}
    missing_capabilities: list[str] = []
    task_text = " ".join([task.title, task.task_type, task.description, *task.tags])

    for claim in actor.expertise_claims:
        claim_hits = [value for value in [claim.domain, claim.method, claim.tool] if value and value in task_text]
        if not claim_hits:
            continue

        domain_score = len(claim_hits) * 2.0
        score += domain_score
        factor_breakdown["domain_match"] += domain_score
        reasons.append(f"匹配专长：{'、'.join(claim_hits)}")

        if claim.verification_status in VERIFIED_STATUSES:
            score += 3.0
            factor_breakdown["verification"] += 3.0
            reasons.append("已验证专长")
        else:
            score += 0.5
            factor_breakdown["verification"] += 0.5
            reasons.append("专长仍处于自评或待验证状态")

        if any("审阅" in supported_role for supported_role in claim.supported_roles):
            score += 0.5
            factor_breakdown["role_fit"] += 0.5
            reasons.append("可承担审阅角色")

        if claim.boundaries:
            missing_capabilities.append(f"边界：{claim.boundaries}")

    for tag in task.tags:
        trust = actor.trust.get(tag)
        if not trust:
            continue
        alpha = trust.get("alpha", 1.0)
        beta = trust.get("beta", 1.0)
        trust_score = alpha / (alpha + beta)
        weighted = trust_score * 4.0
        score += weighted
        factor_breakdown["trust"] += weighted
        reasons.append(f"{tag} 历史信任 {trust_score:.2f}")

    if task.owner_id and actor.id == task.owner_id:
        score += 2.5
        factor_breakdown["role_fit"] += 2.5
        reasons.append("当前任务已指定其为负责人")
    elif actor.id in task.recommended_experts:
        score += 1.5
        factor_breakdown["role_fit"] += 1.5
        reasons.append("当前计划已推荐其承担该任务")

    if actor.actor_type == "ai":
        score += 0.25
        factor_breakdown["ai_assist"] += 0.25
        reasons.append("可作为 AI 协作代理，辅助草稿、结构化和审阅提示")

    score = round(score, 3)
    return RecommendationCandidate(
        actor_id=actor.id,
        actor_name=actor.name,
        actor_type=actor.actor_type,
        score=score,
        reasons=_dedupe(reasons),
        factor_breakdown={key: round(value, 3) for key, value in factor_breakdown.items() if value > 0},
        missing_capabilities=_dedupe(missing_capabilities[:3]),
    )


def _has_relevant_trust(actor: Actor, tags: list[str]) -> bool:
    return any(
        tag in actor.trust and actor.trust[tag].get("alpha", 1.0) + actor.trust[tag].get("beta", 1.0) > 2
        for tag in tags
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _extract_source_refs(text: str) -> list[str]:
    markers = ["来源：", "source:", "Source:", "reference:", "Reference:"]
    for marker in markers:
        if marker in text:
            _, remainder = text.split(marker, 1)
            return [remainder.strip(" 。；;")]
    return []


def _extract_tags(text: str, vocabulary: list[str]) -> list[str]:
    hits = [tag for tag in vocabulary if tag.lower() in text.lower()]
    return hits


def _build_intake_summary(text: str) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return ""
    if "." in normalized:
        sentence = normalized.split(".", 1)[0].strip()
        return sentence[:240]
    if "。" in normalized:
        sentence = normalized.split("。", 1)[0].strip()
        return sentence[:240]
    return normalized[:240]
