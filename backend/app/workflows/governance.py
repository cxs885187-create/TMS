from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain import ApprovalItem

if TYPE_CHECKING:
    from app.repository import InMemoryRepository


def ensure_project_leader(repository: InMemoryRepository, user_id: str, project_id: str, action_label: str) -> None:
    if not repository.is_project_leader(user_id, project_id):
        raise PermissionError(f"只有组长可以{action_label}")


def list_visible_approvals(repository: InMemoryRepository, user_id: str, project_id: str) -> list[ApprovalItem]:
    if not repository.is_project_leader(user_id, project_id):
        return []
    return [item for item in repository.approval_items.values() if item.project_id == project_id]
