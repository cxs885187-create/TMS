from __future__ import annotations

from app.domain import MemoryItem


def build_shared_layer_answer(query: str, shared_memories: list[MemoryItem]) -> tuple[str, list[str]]:
    normalized = query.strip().lower()
    query_keywords = [
        token
        for token in ["批次效应", "Seurat", "空间转录组", "平台比较", "交接", "置信度", "专家网络", "共享记忆"]
        if token.lower() in normalized
    ]
    matched = [
        memory
        for memory in shared_memories
        if _matches_query(normalized, [memory.title, memory.summary, memory.source, *memory.tags])
        or any(keyword.lower() in f"{memory.title} {memory.summary} {' '.join(memory.tags)}".lower() for keyword in query_keywords)
    ]
    if matched:
        answer = "共享层相关内容：" + "；".join(f"{memory.title}：{memory.summary}" for memory in matched[:3])
        return answer, [memory.id for memory in matched[:5]]
    return "当前问题未在共享层找到可直接引用的正式内容。若你在问未验收或未确认资料，请先由组长审核进入共享层。", []


def build_shared_context_ids(shared_memories: list[MemoryItem], limit: int = 12) -> list[str]:
    return [memory.id for memory in shared_memories[:limit]]


def _matches_query(query: str, values: list[str]) -> bool:
    if not query:
        return True
    return any(query in value.lower() for value in values if value)
