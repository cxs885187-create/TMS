from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.repository import InMemoryRepository


class PlanWorkflowService:
    """Compatibility wrapper. Runtime logic is delegated to repository-level helpers."""

    def __init__(self, repository: InMemoryRepository) -> None:
        self.repository = repository

    def run_planning_agent(self, leader_user_id: str, project_id: str, force_generate: bool = False) -> dict[str, object]:
        from app import repository as repository_module

        return repository_module._run_planning_agent_v2(self.repository, leader_user_id, project_id, force_generate)

    def approve_plan(self, leader_user_id: str, project_id: str, plan_id: str, comment: str) -> dict[str, object] | None:
        from app import repository as repository_module

        return repository_module._approve_plan_v2(self.repository, leader_user_id, project_id, plan_id, comment)
