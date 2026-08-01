"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { motion } from "framer-motion";
import {
  Activity,
  Building2,
  Cpu,
  Droplets,
  Factory,
  Network,
  Radio,
  Server,
  Siren,
  TrafficCone,
  Zap,
} from "lucide-react";
import type { AssetStatus } from "@/lib/types";

const ICONS: Record<string, typeof Zap> = {
  power_station: Factory,
  substation_a: Zap,
  substation_b: Zap,
  backup_generator: Activity,
  control_centre: Cpu,
  telecom_hub: Radio,
  data_centre: Server,
  vpn_gateway: Network,
  traffic_mgmt: TrafficCone,
  hospital: Building2,
  water_treatment: Droplets,
  emergency_services: Siren,
};

/** Status drives colour exactly per the PRD token table. */
const STATUS_STYLE: Record<
  AssetStatus,
  { ring: string; text: string; glow: string; label: string }
> = {
  healthy: {
    ring: "border-[var(--ip-grey-400)]",
    text: "text-[var(--ip-grey-400)]",
    glow: "",
    label: "Healthy",
  },
  degraded: {
    ring: "border-[var(--ip-orange)]",
    text: "text-[var(--ip-orange)]",
    glow: "shadow-[0_0_18px_-4px_rgba(249,115,22,0.7)]",
    label: "Degraded",
  },
  failed: {
    ring: "border-[var(--ip-red)]",
    text: "text-[var(--ip-red)]",
    glow: "shadow-[0_0_24px_-2px_rgba(218,30,40,0.85)]",
    label: "Failed",
  },
  hardened: {
    ring: "border-[var(--ip-green)]",
    text: "text-[var(--ip-green)]",
    glow: "shadow-[0_0_18px_-4px_rgba(36,161,72,0.7)]",
    label: "Hardened",
  },
};

export interface AssetNodeData extends Record<string, unknown> {
  label: string;
  assetId: string;
  status: AssetStatus;
  criticality: number;
  findingCount: number;
  isSeed: boolean;
}

export function AssetNode({ data }: NodeProps) {
  const node = data as AssetNodeData;
  const style = STATUS_STYLE[node.status];
  const Icon = ICONS[node.assetId] ?? Server;

  return (
    <motion.div
      initial={false}
      animate={{ scale: node.status === "failed" ? 1.06 : 1 }}
      transition={{ type: "spring", stiffness: 320, damping: 22 }}
      className={`relative w-[176px] rounded-lg border-2 bg-[var(--ip-grey-900)] px-3 py-2.5 ${style.ring} ${style.glow} ${
        node.status === "failed" ? "ip-pulse" : ""
      }`}
      data-testid={`node-${node.assetId}`}
      data-status={node.status}
    >
      <Handle type="target" position={Position.Top} />
      <Handle type="source" position={Position.Bottom} />

      {node.isSeed && (
        <span className="absolute -top-2.5 left-3 rounded bg-[var(--ip-red)] px-1.5 py-0.5 font-mono text-[9px] font-bold tracking-wider text-white">
          SEED
        </span>
      )}
      {node.findingCount > 0 && (
        <span
          title={`${node.findingCount} supply chain finding(s)`}
          className="absolute -top-2 -right-2 flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--ip-orange)] px-1 font-mono text-[10px] font-bold text-black"
        >
          {node.findingCount}
        </span>
      )}

      <div className="flex items-start gap-2">
        <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${style.text}`} strokeWidth={2} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px] leading-tight font-medium text-neutral-100">
            {node.label}
          </div>
          <div className="mt-1 flex items-center justify-between">
            <span className={`font-mono text-[10px] tracking-wide ${style.text}`}>
              {style.label.toUpperCase()}
            </span>
            <span className="font-mono text-[10px] text-neutral-600">
              C{node.criticality}
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
