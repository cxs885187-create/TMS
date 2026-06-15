from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain import ExpertiseMap, ExpertiseMapEdge, ExpertiseMapNode, MapView

if TYPE_CHECKING:
    from app.repository import InMemoryRepository


def build_expertise_map(repository: InMemoryRepository, project_id: str, view: MapView) -> ExpertiseMap:
    active_profiles = [profile for profile in repository.list_expert_profiles(project_id) if profile.status == "active"]
    pending_profiles = [profile for profile in repository.list_expert_profiles(project_id) if profile.status != "active"]
    project_tasks = repository.list_tasks(project_id)
    project_relations = repository.list_expert_relations(project_id)

    if len(active_profiles) < 1:
        return ExpertiseMap(
            view=view,
            supported_views=["person", "topic", "project", "trust"],
            nodes=[
                ExpertiseMapNode(
                    id=f"user:{profile.user_id}",
                    type="Actor",
                    label=repository.get_user(profile.user_id).name if repository.get_user(profile.user_id) else profile.user_id,
                    weight=max(profile.initial_confidence, 0.4),
                )
                for profile in pending_profiles
            ],
            edges=[],
            network_status="candidate_only" if pending_profiles else "pending_profile_approval",
            message="项目内能力仍在待审核阶段，正式专家网络待建立。",
        )

    nodes: list[ExpertiseMapNode] = []
    edges: list[ExpertiseMapEdge] = []

    for profile in active_profiles:
        user = repository.get_user(profile.user_id)
        actor_id = f"user:{profile.user_id}"
        nodes.append(
            ExpertiseMapNode(
                id=actor_id,
                type="Actor",
                label=user.name if user is not None else profile.user_id,
                weight=max(profile.current_confidence, 0.4),
            )
        )
        nodes.append(
            ExpertiseMapNode(
                id=f"expert:{profile.user_id}",
                type="ProjectExpert",
                label=f"{profile.user_id}:{profile.current_confidence:.2f}",
                weight=profile.current_confidence,
            )
        )
        edges.append(ExpertiseMapEdge(source=actor_id, target=f"expert:{profile.user_id}", type="project_confidence", weight=profile.current_confidence))
        for claim in profile.structured_capabilities:
            domain_id = f"domain:{claim.domain}"
            method_id = f"method:{claim.method}"
            tool_id = f"tool:{claim.tool}"
            nodes.extend(
                [
                    ExpertiseMapNode(id=domain_id, type="Domain", label=claim.domain),
                    ExpertiseMapNode(id=method_id, type="Method", label=claim.method),
                    ExpertiseMapNode(id=tool_id, type="Tool", label=claim.tool),
                ]
            )
            edges.extend(
                [
                    ExpertiseMapEdge(source=actor_id, target=domain_id, type="claims_expertise_in", weight=claim.self_confidence),
                    ExpertiseMapEdge(source=actor_id, target=method_id, type="applied_in", weight=1.0),
                    ExpertiseMapEdge(source=actor_id, target=tool_id, type="applied_in", weight=1.0),
                ]
            )

    if view == "project":
        for task in project_tasks:
            nodes.append(ExpertiseMapNode(id=task.id, type="Outcome", label=task.title))
            if task.owner_id:
                edges.append(ExpertiseMapEdge(source=f"user:{task.owner_id}", target=task.id, type="contributed_to", weight=1.0))

    if view == "trust":
        for relation in project_relations:
            edges.append(
                ExpertiseMapEdge(
                    source=f"user:{relation.from_user_id}",
                    target=f"user:{relation.to_user_id}",
                    type=relation.relation_type,
                    weight=relation.weight,
                )
            )
    elif view in {"person", "project"}:
        for relation in project_relations:
            edges.append(
                ExpertiseMapEdge(
                    source=f"user:{relation.from_user_id}",
                    target=f"user:{relation.to_user_id}",
                    type=relation.relation_type,
                    weight=relation.weight,
                )
            )

    if view == "topic":
        nodes = [node for node in nodes if node.type in {"Actor", "Domain", "Method", "Tool"}]
        valid = {node.id for node in nodes}
        edges = [edge for edge in edges if edge.source in valid and edge.target in valid]
    elif view == "person":
        nodes = [node for node in nodes if node.type in {"Actor", "ProjectExpert", "Domain", "Method", "Tool"}]
        valid = {node.id for node in nodes}
        edges = [edge for edge in edges if edge.source in valid and edge.target in valid]
    elif view == "project":
        nodes = [node for node in nodes if node.type in {"Actor", "ProjectExpert", "Outcome"}]
        valid = {node.id for node in nodes}
        edges = [edge for edge in edges if edge.source in valid and edge.target in valid]
    elif view == "trust":
        nodes = [node for node in nodes if node.type in {"Actor"}]
        valid = {node.id for node in nodes}
        edges = [edge for edge in edges if edge.source in valid and edge.target in valid]

    deduped_nodes = list({(node.id, node.type): node for node in nodes}.values())
    node_ids = {node.id for node in deduped_nodes}
    deduped_edges = list({(edge.source, edge.target, edge.type): edge for edge in edges if edge.source in node_ids and edge.target in node_ids}.values())
    return ExpertiseMap(
        view=view,
        supported_views=["person", "topic", "project", "trust"],
        nodes=deduped_nodes,
        edges=deduped_edges,
        network_status="active",
        message="当前专家网络仅基于项目内已审核能力与协作关系生成。",
    )
