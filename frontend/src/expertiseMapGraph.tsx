import { useMemo, useState } from "react";

import type { ExpertiseMap, ExpertiseMapEdge, ExpertiseMapNode } from "./types";

type Point = {
  x: number;
  y: number;
};

const nodeTypeLabels: Record<string, string> = {
  Actor: "成员",
  ProjectExpert: "项目专家",
  Domain: "领域",
  Method: "方法",
  Tool: "工具",
  Outcome: "任务结果",
  TrustContext: "信任上下文",
};

const nodeTypeColors: Record<string, string> = {
  Actor: "#2f5d50",
  ProjectExpert: "#d87a42",
  Domain: "#3f7d95",
  Method: "#5f7f52",
  Tool: "#7f5c9a",
  Outcome: "#8d4d3f",
  TrustContext: "#a6652e",
};

const edgeTypeColors: Record<string, string> = {
  claims_expertise_in: "#5e7a6c",
  applied_in: "#86a294",
  contributed_to: "#d87a42",
  project_confidence: "#a6652e",
  can_handoff_to: "#5d7489",
  can_review: "#2f5d50",
  depends_on: "#8d4d3f",
  high_trust: "#a6652e",
  needs_support_from: "#7f5c9a",
  trusts_in: "#c08a55",
};

const viewTypeOrder: Record<ExpertiseMap["view"], string[]> = {
  person: ["Actor", "ProjectExpert", "Domain", "Method", "Tool"],
  topic: ["Domain", "Method", "Tool", "Actor"],
  project: ["Actor", "ProjectExpert", "Outcome"],
  trust: ["Actor", "TrustContext"],
};

function getNodeRadius(node: ExpertiseMapNode) {
  const base = 16;
  return Math.max(base, Math.min(28, base + node.weight * 10));
}

function buildLayout(map: ExpertiseMap) {
  const preferredOrder = viewTypeOrder[map.view];
  const grouped = new Map<string, ExpertiseMapNode[]>();

  for (const node of map.nodes) {
    const items = grouped.get(node.type) ?? [];
    items.push(node);
    grouped.set(node.type, items);
  }

  const orderedTypes = [
    ...preferredOrder.filter((type) => grouped.has(type)),
    ...Array.from(grouped.keys()).filter((type) => !preferredOrder.includes(type)),
  ];

  const width = Math.max(860, orderedTypes.length * 220);
  const maxRows = Math.max(1, ...orderedTypes.map((type) => grouped.get(type)?.length ?? 0));
  const height = Math.max(360, maxRows * 112);
  const positions: Record<string, Point> = {};
  const paddingX = 96;
  const paddingY = 72;
  const columnGap = orderedTypes.length > 1 ? (width - paddingX * 2) / (orderedTypes.length - 1) : 0;

  orderedTypes.forEach((type, columnIndex) => {
    const nodes = grouped.get(type) ?? [];
    const x = orderedTypes.length > 1 ? paddingX + columnGap * columnIndex : width / 2;
    const rowGap = nodes.length > 1 ? (height - paddingY * 2) / (nodes.length - 1) : 0;
    const startY = nodes.length > 1 ? paddingY : height / 2;

    nodes.forEach((node, rowIndex) => {
      positions[node.id] = {
        x,
        y: nodes.length > 1 ? startY + rowGap * rowIndex : startY,
      };
    });
  });

  return { width, height, positions, orderedTypes };
}

function buildNodeSummary(node: ExpertiseMapNode, edges: ExpertiseMapEdge[]) {
  const related = edges.filter((edge) => edge.source === node.id || edge.target === node.id);
  return {
    title: node.label,
    type: nodeTypeLabels[node.type] ?? node.type,
    weight: node.weight,
    related,
  };
}

export function ExpertiseMapGraph({
  map,
  className,
  legendClassName,
}: {
  map: ExpertiseMap;
  className?: string;
  legendClassName?: string;
}) {
  const { width, height, positions } = useMemo(() => buildLayout(map), [map]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const effectiveSelectedNodeId = selectedNodeId && positions[selectedNodeId] ? selectedNodeId : map.nodes[0]?.id ?? null;
  const selectedNode = map.nodes.find((node) => node.id === effectiveSelectedNodeId) ?? null;
  const selectedSummary = selectedNode ? buildNodeSummary(selectedNode, map.edges) : null;
  const legendTypes = Array.from(new Set(map.nodes.map((node) => node.type)));

  return (
    <div className={className}>
      <div className="graph-summary">
        <strong>
          {map.network_status === "active"
            ? "正式项目网络"
            : map.network_status === "candidate_only"
              ? "候选能力网络"
              : "待建立网络"}
        </strong>
        <span>{map.message}</span>
      </div>
      <svg className="graph-canvas" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="专家网络关系图">
        {map.edges.map((edge) => {
          const source = positions[edge.source];
          const target = positions[edge.target];
          if (!source || !target) return null;
          const isActive =
            effectiveSelectedNodeId !== null &&
            (edge.source === effectiveSelectedNodeId || edge.target === effectiveSelectedNodeId);
          return (
            <line
              key={`${edge.source}-${edge.target}-${edge.type}`}
              className={isActive ? "graph-edge active" : "graph-edge"}
              stroke={edgeTypeColors[edge.type] ?? "#91a39a"}
              strokeWidth={Math.max(1.5, edge.weight * 2.2)}
              x1={source.x}
              x2={target.x}
              y1={source.y}
              y2={target.y}
            />
          );
        })}

        {map.nodes.map((node) => {
          const point = positions[node.id];
          if (!point) return null;
          const isActive = node.id === effectiveSelectedNodeId;
          const radius = getNodeRadius(node);
          return (
            <g
              key={node.id}
              className={isActive ? "graph-node active" : "graph-node"}
              onClick={() => setSelectedNodeId(node.id)}
              transform={`translate(${point.x}, ${point.y})`}
            >
              <circle fill={nodeTypeColors[node.type] ?? "#5e7a6c"} r={radius} />
              <text className="graph-node-label" dy={radius + 18} textAnchor="middle">
                {node.label}
              </text>
              <title>{`${node.label} / ${nodeTypeLabels[node.type] ?? node.type}`}</title>
            </g>
          );
        })}
      </svg>

      <div className={legendClassName}>
        <div>
          <strong>图例</strong>
          <div className="graph-legend-grid">
            {legendTypes.map((type) => (
              <div className="graph-legend-item" key={type}>
                <span className="graph-legend-dot" style={{ background: nodeTypeColors[type] ?? "#5e7a6c" }} />
                <span>{nodeTypeLabels[type] ?? type}</span>
              </div>
            ))}
          </div>
        </div>

        {selectedSummary && (
          <div className="graph-node-panel">
            <strong>{selectedSummary.title}</strong>
            <span>{selectedSummary.type}</span>
            <small>权重：{selectedSummary.weight.toFixed(2)}</small>
            <small>关联关系：{selectedSummary.related.length}</small>
            {selectedSummary.related.slice(0, 4).map((edge) => (
              <small key={`${edge.source}-${edge.target}-${edge.type}`}>
                {edge.source} → {edge.target} / {edge.type}
              </small>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
