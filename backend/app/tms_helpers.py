from __future__ import annotations

from app.domain import ExpertiseClaim


def infer_capability_claims(raw_text: str, proof_text: str) -> list[ExpertiseClaim]:
    text = f"{raw_text}\n{proof_text}".lower()
    candidates = [
        ("肿瘤免疫", "流式分析", "FlowJo"),
        ("单细胞分析", "Seurat 流程", "R"),
        ("空间转录组", "文献整理", "PDF"),
        ("统计审阅", "方法检查", "LLM"),
    ]
    claims: list[ExpertiseClaim] = []
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
                level="可协作" if hits == 1 else "可独立完成",
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


def compute_initial_confidence(raw_text: str, proof_text: str, project_summary: str, claims: list[object]) -> dict[str, float]:
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
