"use client";

import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import { useMemo } from "react";
import { AssetNode, type AssetNodeData } from "./AssetNode";
import type { Asset, AssetStatus, CascadeResult, Dependency } from "@/lib/types";

const nodeTypes = { asset: AssetNode };

const EDGE_STYLE: Record<Dependency["dependency_type"], { dash?: string; hue: string }> = {
  power: { hue: "#0f62fe" },
  comms: { dash: "8 4", hue: "#5a8dee" },
  operational: { dash: "2 4", hue: "#7c8794" },
};

interface Props {
  assets: Asset[];
  dependencies: Dependency[];
  statuses: Record<string, AssetStatus> | null;
  result: CascadeResult | null;
  findingCounts: Record<string, number>;
  onSelect: (assetId: string) => void;
}

export function InfraGraph({
  assets,
  dependencies,
  statuses,
  result,
  findingCounts,
  onSelect,
}: Props) {
  const nodes = useMemo<Node<AssetNodeData>[]>(
    () =>
      assets.map((asset) => ({
        id: asset.id,
        type: "asset",
        // Fixed positions from the database keep the layout byte-identical
        // across reloads (F1 AC#4).
        position: { x: asset.position_x, y: asset.position_y },
        data: {
          label: asset.name,
          assetId: asset.id,
          status: statuses?.[asset.id] ?? asset.status,
          criticality: asset.criticality,
          findingCount: findingCounts[asset.id] ?? 0,
          isSeed: result?.seed_assets.includes(asset.id) ?? false,
        },
        draggable: false,
      })),
    [assets, statuses, findingCounts, result],
  );

  const edges = useMemo<Edge[]>(() => {
    const failed = new Set(result?.failed ?? []);
    const impacted = new Set(result?.newly_impacted ?? []);
    const path = result?.critical_path ?? [];
    const onCriticalPath = new Set(
      path.slice(0, -1).map((node, index) => `${node}->${path[index + 1]}`),
    );

    return dependencies.map((dep) => {
      const key = `${dep.source}->${dep.target}`;
      const carried = failed.has(dep.source) && impacted.has(dep.target);
      const critical = onCriticalPath.has(key);
      const base = EDGE_STYLE[dep.dependency_type];

      return {
        id: `${key}-${dep.dependency_type}`,
        source: dep.source,
        target: dep.target,
        animated: carried,
        style: {
          stroke: carried ? "var(--ip-red)" : base.hue,
          strokeWidth: critical ? 3 : carried ? 2.2 : 1.3,
          strokeDasharray: carried ? undefined : base.dash,
          opacity: carried ? 1 : result ? 0.28 : 0.6,
        },
      };
    });
  }, [dependencies, result]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      // Extra padding keeps the bottom row of assets clear of the floating
      // impact strip at 1280x720, the projector target.
      fitViewOptions={{ padding: 0.17 }}
      minZoom={0.3}
      maxZoom={1.6}
      proOptions={{ hideAttribution: true }}
      nodesDraggable={false}
      onNodeClick={(_, node) => onSelect(node.id)}
    >
      <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#242424" />
      {/* No MiniMap: twelve nodes all fit on screen, so it only ate space
          and competed with the impact strip on a 720p projector. */}
      <Controls showInteractive={false} position="top-left" />
    </ReactFlow>
  );
}
