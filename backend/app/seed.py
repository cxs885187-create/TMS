from __future__ import annotations

from app.domain import (
    Actor,
    Decision,
    Evidence,
    ExpertiseClaim,
    HandoverBundle,
    MemoryItem,
    Project,
    ProjectMember,
    TMSWorkflow,
    Task,
    TermEntry,
    User,
    WorkflowStep,
)


def seed_projects() -> list[Project]:
    return [
        Project(
            id="p1",
            name="肿瘤微环境研究课题 A",
            owner_user_id="u3",
            stage="实验设计",
            summary="围绕肿瘤微环境中的免疫细胞状态变化，组织文献、实验与写作证据链。",
            risks=["批次效应需要复核", "空间转录组方法边界尚未确认"],
            research_questions=["免疫细胞状态变化是否与治疗响应相关", "流式验证方案如何覆盖关键亚群"],
            milestones=["完成文献框架", "完成流式验证实验设计", "形成写作证据链"],
        ),
        Project(
            id="p2",
            name="空间转录组方法预研",
            owner_user_id="u3",
            stage="文献研读",
            summary="比较空间转录组常用平台、分析流程和适用边界，为后续课题立项做准备。",
            risks=["样本量估计尚未完成", "平台成本和数据质量需要进一步确认"],
            research_questions=["不同平台在样本条件与分辨率上如何权衡", "哪些分析流程适合当前课题"],
            milestones=["平台比较表", "样本要求清单", "预研交接包"],
        ),
    ]


def seed_project_members() -> list[ProjectMember]:
    return [
        ProjectMember(id="pm-1", project_id="p1", user_id="u3", role="leader"),
        ProjectMember(id="pm-2", project_id="p1", user_id="u1", role="member"),
        ProjectMember(id="pm-3", project_id="p1", user_id="u2", role="member"),
        ProjectMember(id="pm-4", project_id="p2", user_id="u3", role="leader"),
        ProjectMember(id="pm-5", project_id="p2", user_id="u2", role="member"),
    ]


def seed_users() -> list[User]:
    return [
        User(
            id="u1",
            name="王博士",
            role="研究员",
            actor_id="a1",
            project_ids=["p1"],
            permission_profile="researcher",
        ),
        User(
            id="u2",
            name="李同学",
            role="博士生",
            actor_id="a2",
            project_ids=["p1", "p2"],
            permission_profile="student",
        ),
        User(
            id="u3",
            name="张老师",
            role="PI / 课题负责人",
            actor_id="a3",
            project_ids=["p1", "p2"],
            permission_profile="pi",
        ),
    ]


def seed_actors() -> list[Actor]:
    return [
        Actor(
            id="a1",
            name="王博士",
            actor_type="human",
            role="研究员",
            affiliation="肿瘤免疫组",
            expertise_claims=[
                ExpertiseClaim(
                    id="claim-a1-1",
                    domain="肿瘤免疫",
                    method="流式分析",
                    tool="FlowJo",
                    level="可指导他人",
                    evidence=["既往项目 P-001", "实验记录 EXP-019"],
                    recency="2026-05",
                    supported_roles=["主导", "审阅"],
                    boundaries="不覆盖单细胞测序分析",
                    self_confidence=0.82,
                    verification_status="已验证",
                    peer_confirmations=["张老师"],
                    behavioral_evidence=["t2", "m1"],
                    outcome_validation=["d1"],
                    review_status="已确认",
                )
            ],
            trust={"肿瘤免疫": {"alpha": 8, "beta": 2}, "流式分析": {"alpha": 7, "beta": 2}},
            verified_expertise_profiles=["claim-a1-1"],
            contribution_summary="负责实验设计和流式审阅。",
        ),
        Actor(
            id="a2",
            name="李同学",
            actor_type="human",
            role="博士生",
            affiliation="单细胞分析组",
            expertise_claims=[
                ExpertiseClaim(
                    id="claim-a2-1",
                    domain="单细胞分析",
                    method="Seurat 流程",
                    tool="R",
                    level="可独立完成",
                    evidence=["分析脚本 ANA-004"],
                    recency="2026-05",
                    supported_roles=["协作", "执行"],
                    boundaries="不负责统计方案最终审阅",
                    self_confidence=0.74,
                    verification_status="同行确认",
                    peer_confirmations=["王博士"],
                    behavioral_evidence=["t1", "m2"],
                    outcome_validation=[],
                    review_status="已确认",
                )
            ],
            trust={"单细胞分析": {"alpha": 6, "beta": 2}, "Seurat": {"alpha": 5, "beta": 2}},
            verified_expertise_profiles=["claim-a2-1"],
            contribution_summary="负责文献整理和预分析执行。",
        ),
        Actor(
            id="a3",
            name="张老师",
            actor_type="human",
            role="PI / 课题负责人",
            affiliation="课题负责人",
            expertise_claims=[
                ExpertiseClaim(
                    id="claim-a3-1",
                    domain="研究治理",
                    method="方案审阅",
                    tool="人工审阅",
                    level="最终把关",
                    evidence=["项目审批记录"],
                    recency="2026-06",
                    supported_roles=["审批", "审阅"],
                    boundaries="不替代具体分析执行",
                    self_confidence=0.95,
                    verification_status="已验证",
                    peer_confirmations=[],
                    behavioral_evidence=["d1", "w5"],
                    outcome_validation=["handover-p1-1"],
                    review_status="已确认",
                )
            ],
            trust={"研究治理": {"alpha": 10, "beta": 1}},
            verified_expertise_profiles=["claim-a3-1"],
            contribution_summary="负责共享记忆、术语与关键决策审批。",
        ),
        Actor(
            id="ai1",
            name="统计审阅助手",
            actor_type="ai",
            role="AI 协作代理",
            affiliation="系统内置",
            expertise_claims=[
                ExpertiseClaim(
                    id="claim-ai1-1",
                    domain="统计审阅",
                    method="方法检查",
                    tool="LLM",
                    level="可协作",
                    evidence=["系统配置"],
                    recency="2026-06",
                    supported_roles=["审阅", "协作"],
                    boundaries="不能单独批准正式结论",
                    self_confidence=0.65,
                    verification_status="系统验证增强",
                    peer_confirmations=[],
                    behavioral_evidence=[],
                    outcome_validation=[],
                    review_status="已确认",
                )
            ],
            trust={"统计审阅": {"alpha": 5, "beta": 2}},
            contribution_summary="仅用于草稿生成、结构化提取与审阅提示，不承担正式审批与最终结论责任。",
        ),
    ]


def seed_tasks() -> list[Task]:
    return [
        Task(
            id="t1",
            project_id="p1",
            title="完成单细胞文献对照表",
            task_type="文献研读",
            description="整理肿瘤微环境单细胞研究中的样本设计、分析流程和局限性。",
            status="进行中",
            tags=["单细胞分析", "肿瘤免疫", "Seurat"],
            owner_id="a2",
            review_status="待审阅",
            next_action="补充方法适用边界后提交审阅",
            initiator="a3",
            required_roles=["执行", "审阅"],
            recommended_experts=["a2", "a1"],
            outputs=["m2"],
        ),
        Task(
            id="t2",
            project_id="p1",
            title="设计流式验证实验",
            task_type="实验设计",
            description="根据当前假设设计免疫细胞状态验证实验。",
            status="待分派",
            tags=["肿瘤免疫", "流式分析"],
            review_status="草稿",
            next_action="请求王博士审阅实验条件",
            initiator="a3",
            required_roles=["主导", "审阅"],
        ),
        Task(
            id="t3",
            project_id="p2",
            title="整理空间转录组平台差异",
            task_type="文献研读",
            description="比较 Visium、MERFISH 与 Stereo-seq 的样本要求、分辨率和分析边界。",
            status="待审阅",
            tags=["空间转录组", "文献研读"],
            owner_id="a2",
            review_status="待审阅",
            next_action="补充平台成本和样本制备风险",
            initiator="a3",
            required_roles=["执行", "审阅"],
        ),
    ]


def seed_memories() -> list[MemoryItem]:
    return [
        MemoryItem(
            id="m1",
            project_id="p1",
            memory_layer="shared",
            memory_type="实验记忆",
            title="实验条件变更导致批次偏移",
            summary="5 月 20 日批次中抗体孵育时间变化可能影响后续比较，需要在分析中单独标注。",
            source="2026-05-20 实验记录 + 复现实验",
            source_or_provenance="实验记录本 + 复现实验",
            confidence="高",
            review_status="已确认",
            tags=["流式分析", "批次效应"],
            linked_evidence=["e1"],
            actors_involved=["a1", "a2"],
            next_action_or_implication="在正式分析中将该批次单独标注。",
            shared=True,
        ),
        MemoryItem(
            id="m2",
            project_id="p1",
            memory_type="文献记忆",
            title="Seurat 预分析适合早期探索",
            summary="当前项目可先使用 Seurat 进行探索性聚类，但正式结论需要补充批次校正与复现说明。",
            source="三篇文献 + 组会讨论",
            source_or_provenance="文献笔记 + 组会纪要",
            confidence="中",
            review_status="待审阅",
            tags=["单细胞分析", "Seurat"],
            linked_evidence=["e2"],
            actors_involved=["a2", "a1"],
            next_action_or_implication="补充批次校正比较后再决定是否共享。",
        ),
        MemoryItem(
            id="m3",
            project_id="p2",
            memory_type="文献记忆",
            title="空间转录组平台选择需要结合样本类型",
            summary="不同平台在分辨率、通量、成本和组织兼容性上差异明显，不能只按文献热度选择。",
            source="方法综述 + 供应商技术说明",
            source_or_provenance="综述文献 + 技术说明",
            confidence="中",
            review_status="待审阅",
            tags=["空间转录组", "平台比较"],
            linked_evidence=["e3"],
            actors_involved=["a2"],
            next_action_or_implication="补充真实报价和样本制备要求。",
        ),
    ]


def seed_decisions() -> list[Decision]:
    return [
        Decision(
            id="d1",
            project_id="p1",
            title="先采用 Seurat 流程做预分析",
            decision_body="项目早期先使用 Seurat 流程完成探索性分析，再决定是否加入更复杂的批次校正策略。",
            rationale="当前证据足以支持探索性分析，但不足以支持正式结论。",
            approval_status="已通过",
            linked_evidence=["e2"],
            risk_notes=["后续需要验证批次校正策略"],
            alternatives=["直接引入更复杂批次校正流程"],
            approvers=["a3"],
        ),
        Decision(
            id="d2",
            project_id="p2",
            title="先完成平台比较再进入实验设计",
            decision_body="空间转录组预研阶段先完成平台比较表和样本要求清单，暂不进入实验排期。",
            rationale="当前证据不足以决定平台，先降低错误采购和错误设计风险。",
            approval_status="待审批",
            linked_evidence=["e3"],
            risk_notes=["需要补充真实报价和样本制备条件"],
            alternatives=["先锁定 Visium 并进入实验排期"],
        ),
    ]


def seed_evidence() -> list[Evidence]:
    return [
        Evidence(
            id="e1",
            project_id="p1",
            evidence_type="实验记录",
            title="2026-05-20 流式实验记录",
            source="实验记录本",
            verification_status="已验证",
            linked_objects=["m1"],
            created_by="a1",
        ),
        Evidence(
            id="e2",
            project_id="p1",
            evidence_type="文献与讨论",
            title="Seurat 预分析依据包",
            source="文献笔记 + 组会纪要",
            verification_status="待复核",
            linked_objects=["m2", "d1"],
            created_by="a2",
        ),
        Evidence(
            id="e3",
            project_id="p2",
            evidence_type="方法综述",
            title="空间转录组平台比较资料",
            source="文献综述 + 平台技术说明",
            verification_status="待复核",
            linked_objects=["m3", "d2"],
            created_by="a2",
        ),
    ]


def seed_terms() -> list[TermEntry]:
    return [
        TermEntry(
            id="term-team-1",
            canonical_term="肿瘤微环境",
            aliases=["TME", "tumor microenvironment"],
            domain_scope="肿瘤免疫",
            definition="指肿瘤组织内免疫细胞、基质细胞和分子信号构成的局部生态。",
            related_terms=["免疫细胞状态", "批次效应"],
            do_not_confuse_with=["肿瘤细胞内环境"],
            example_usage="讨论免疫细胞状态时统一使用肿瘤微环境这一术语。",
            owner="张老师",
            reviewer="王博士",
            level="team",
        ),
        TermEntry(
            id="term-project-1",
            canonical_term="平台比较",
            aliases=["platform comparison"],
            domain_scope="空间转录组",
            definition="在样本要求、分辨率、通量、成本和分析边界上比较不同平台。",
            related_terms=["空间分辨率", "样本要求"],
            do_not_confuse_with=["供应商宣传资料"],
            example_usage="进入实验设计前必须完成平台比较。",
            owner="李同学",
            reviewer="张老师",
            level="project",
            project_id="p2",
        ),
    ]


def seed_handover_bundles() -> list[HandoverBundle]:
    return [
        HandoverBundle(
            id="handover-p1-1",
            project_id="p1",
            summary="已确认批次效应风险，Seurat 仅用于预分析，正式结论仍待批次校正补强。",
            key_members=["王博士", "李同学", "张老师"],
            critical_decisions=["先采用 Seurat 流程做预分析"],
            key_memories=["实验条件变更导致批次偏移"],
            open_questions=["补充批次校正比较后再决定是否共享。"],
            risk_items=["批次效应需要复核"],
            review_status="待审阅",
            generated_from=["m1", "m2", "d1"],
        )
    ]


def seed_workflows() -> list[TMSWorkflow]:
    return [
        TMSWorkflow(
            id="w1",
            project_id="p1",
            loop_type="问题进入",
            title="流式验证方案问题闭环",
            description="从任务问题进入，完成专家推荐、协作回答、结果沉淀和 trust 更新。",
            related_object_id="t2",
            steps=[
                WorkflowStep(id="w1-s1", title="问题进入", status="进行中", required_output="明确任务目标、标签和边界"),
                WorkflowStep(id="w1-s2", title="推荐专家", required_output="确认主专家、协作成员和审阅人"),
                WorkflowStep(id="w1-s3", title="协作产出", required_output="形成可审阅的方案或结论"),
                WorkflowStep(id="w1-s4", title="沉淀记忆", required_output="把结果写入结构化记忆或决策"),
                WorkflowStep(id="w1-s5", title="更新信任", required_output="根据审阅结果记录贡献与 trust 事件"),
            ],
            current_state="under_review",
        ),
        TMSWorkflow(
            id="w2",
            project_id="p1",
            loop_type="文献进入",
            title="单细胞文献进入闭环",
            description="文献输入后生成强模板草稿，经人工确认后进入团队记忆。",
            related_object_id="m2",
            steps=[
                WorkflowStep(id="w2-s1", title="录入来源", status="进行中", required_output="补全文献来源、摘要和方法字段"),
                WorkflowStep(id="w2-s2", title="生成草稿", required_output="形成文献记忆草稿"),
                WorkflowStep(id="w2-s3", title="人工审阅", required_output="确认可引用主张、局限性和证据"),
                WorkflowStep(id="w2-s4", title="关联任务", required_output="绑定后续任务或研究假设"),
            ],
            current_state="draft",
        ),
        TMSWorkflow(
            id="w3",
            project_id="p1",
            loop_type="实验闭环",
            title="批次效应复核实验闭环",
            description="实验记录进入验证流程，确认后固化为可复用的 procedural memory。",
            related_object_id="m1",
            steps=[
                WorkflowStep(id="w3-s1", title="记录过程", status="进行中", required_output="补齐材料、步骤、异常和结果"),
                WorkflowStep(id="w3-s2", title="结果验证", required_output="审阅复现实验或统计检查"),
                WorkflowStep(id="w3-s3", title="固化经验", required_output="沉淀为 procedural memory"),
            ],
            current_state="approved",
        ),
        TMSWorkflow(
            id="w4",
            project_id="p1",
            loop_type="写作闭环",
            title="预分析写作证据闭环",
            description="把主张、证据、作者与审阅者串成可追溯链条。",
            related_object_id="d1",
            steps=[
                WorkflowStep(id="w4-s1", title="提出主张", status="进行中", required_output="写出待支持的段落主张"),
                WorkflowStep(id="w4-s2", title="绑定证据", required_output="关联文献、实验和讨论证据"),
                WorkflowStep(id="w4-s3", title="人工确认", required_output="作者和审阅者确认可写入稿件"),
            ],
            current_state="under_review",
        ),
        TMSWorkflow(
            id="w5",
            project_id="p1",
            loop_type="交接闭环",
            title="阶段交接闭环",
            description="汇总关键记忆、决策和风险，生成交接包并等待负责人审核。",
            related_object_id="handover-p1-1",
            steps=[
                WorkflowStep(id="w5-s1", title="汇总上下文", status="进行中", required_output="整理关键成员、记忆、决策和风险"),
                WorkflowStep(id="w5-s2", title="生成交接包", required_output="形成交接包草稿"),
                WorkflowStep(id="w5-s3", title="审核发布", required_output="负责人确认后发布给新成员"),
                WorkflowStep(id="w5-s4", title="反馈修订", required_output="新成员反馈遗漏点并修订记忆结构"),
            ],
            current_state="draft",
        ),
        TMSWorkflow(
            id="w6",
            project_id="p2",
            loop_type="问题进入",
            title="空间转录组平台选择问题闭环",
            description="围绕平台选择问题推荐候选专家，并沉淀比较结论。",
            related_object_id="t3",
            steps=[
                WorkflowStep(id="w6-s1", title="问题进入", status="进行中", required_output="明确平台比较维度"),
                WorkflowStep(id="w6-s2", title="推荐专家", required_output="确认方法和成本审阅候选人"),
                WorkflowStep(id="w6-s3", title="沉淀结论", required_output="形成平台比较记忆"),
            ],
            current_state="draft",
        ),
        TMSWorkflow(
            id="w7",
            project_id="p2",
            loop_type="文献进入",
            title="平台综述文献进入闭环",
            description="把平台综述资料结构化为可审阅文献记忆。",
            related_object_id="m3",
            steps=[
                WorkflowStep(id="w7-s1", title="录入来源", status="进行中", required_output="补齐综述和技术说明来源"),
                WorkflowStep(id="w7-s2", title="人工审阅", required_output="确认平台边界和适用样本"),
            ],
            current_state="draft",
        ),
        TMSWorkflow(
            id="w8",
            project_id="p2",
            loop_type="实验闭环",
            title="预实验可行性闭环",
            description="在进入实验排期前验证样本条件和平台约束。",
            related_object_id=None,
            steps=[
                WorkflowStep(id="w8-s1", title="定义验证项", status="进行中", required_output="列出样本质量、成本、分辨率验证项"),
                WorkflowStep(id="w8-s2", title="确认条件", required_output="负责人确认是否进入实验设计"),
            ],
            current_state="draft",
        ),
        TMSWorkflow(
            id="w9",
            project_id="p2",
            loop_type="写作闭环",
            title="平台比较汇报写作闭环",
            description="把平台比较主张绑定证据，形成汇报材料。",
            related_object_id="d2",
            steps=[
                WorkflowStep(id="w9-s1", title="提出主张", status="进行中", required_output="写出平台选择建议"),
                WorkflowStep(id="w9-s2", title="绑定证据", required_output="关联综述、报价和样本要求证据"),
            ],
            current_state="draft",
        ),
        TMSWorkflow(
            id="w10",
            project_id="p2",
            loop_type="交接闭环",
            title="预研交接闭环",
            description="为后续立项成员整理平台比较、未决问题和风险。",
            related_object_id=None,
            steps=[
                WorkflowStep(id="w10-s1", title="汇总上下文", status="进行中", required_output="整理平台比较表、决策和风险"),
                WorkflowStep(id="w10-s2", title="生成交接包", required_output="形成预研交接包草稿"),
            ],
            current_state="draft",
        ),
    ]
