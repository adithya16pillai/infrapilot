"use client";

import Link from "next/link";
import type { ImpactComparison, SupplyChainFinding } from "@/lib/types";

function Side({
  finding,
  emphasis,
}: {
  finding: SupplyChainFinding;
  emphasis: boolean;
}) {
  return (
    <Link
      href={`/city?asset=${finding.asset_id}`}
      className={`block rounded-lg border p-3.5 transition hover:border-[var(--ip-blue)] ${
        emphasis
          ? "border-[var(--ip-orange)]/60 bg-[var(--ip-orange)]/5"
          : "border-[var(--ip-grey-700)] bg-black/20"
      }`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-[12px] text-neutral-100">
          {finding.package}
        </span>
        <span className="rounded border border-[var(--ip-red)]/50 px-1.5 py-0.5 font-mono text-[9px] text-[var(--ip-red)] uppercase">
          {finding.severity}
        </span>
      </div>

      <p className="mt-1 text-[12px] text-neutral-400">on {finding.asset_name}</p>

      <div className="mt-3 flex items-baseline gap-1.5">
        <span
          className={`font-mono text-3xl leading-none font-bold ${
            emphasis ? "text-[var(--ip-orange)]" : "text-neutral-500"
          }`}
        >
          {finding.operational_impact}
        </span>
        <span className="font-mono text-[9px] tracking-wider text-neutral-600 uppercase">
          operational impact
        </span>
      </div>

      <p className="mt-2 font-mono text-[10px] leading-relaxed text-neutral-500">
        severity ×{finding.severity_weight} · downstream criticality{" "}
        {finding.downstream_criticality}
      </p>

      <p className="mt-2 border-t border-[var(--ip-grey-700)] pt-2 font-mono text-[10px] leading-relaxed text-neutral-400">
        {finding.chain_names.length > 1
          ? finding.chain_names.join(" → ")
          : "no downstream cascade"}
      </p>
    </Link>
  );
}

/**
 * The argument for the whole supply chain layer, in one panel: OSSPrey says
 * these two findings are the same severity; the cascade says they are not the
 * same problem.
 */
export function OspreyComparison({ comparison }: { comparison: ImpactComparison }) {
  return (
    <div>
      <div className="grid grid-cols-2 gap-3">
        <Side finding={comparison.higher} emphasis />
        <Side finding={comparison.lower} emphasis={false} />
      </div>
      <p className="mt-3 rounded-md border border-[var(--ip-blue)]/30 bg-[var(--ip-blue)]/5 px-3 py-2.5 text-[12px] leading-relaxed text-neutral-300">
        {comparison.explanation}
      </p>
    </div>
  );
}

/**
 * Explains what OSSPrey actually detects, so the ranking above is not mistaken
 * for a CVE feed. OSSPrey's model is behavioural — it catches malicious
 * packages by what they do, including ones that carry no CVE at all.
 */
export function OspreyExplainer({ mode }: { mode: "mock" | "live" }) {
  return (
    <div className="space-y-2.5 text-[12px] leading-relaxed text-neutral-400">
      <p>
        <span className="font-medium text-neutral-200">OSSPrey</span> detects
        malicious open source packages by <em>behaviour</em> rather than by
        matching known CVEs — install-time filesystem writes, obfuscated
        payloads, maintainer-handover takeover patterns. That catches
        compromised releases that carry no CVE at all, which is most of the
        supply chain attacks that actually land.
      </p>
      <p>
        A behavioural severity tells you{" "}
        <span className="text-neutral-200">how malicious</span> a package is. It
        cannot tell you{" "}
        <span className="text-neutral-200">how much it matters to this city</span>
        . InfraPilot supplies the second half: it runs the cascade from the host
        asset and weights each finding by the criticality it would actually take
        down, so patch order follows operational consequence instead of severity
        alone.
      </p>
      <p className="font-mono text-[10.5px] text-neutral-500">
        impact = severity_weight × downstream_criticality(asset)
      </p>
      <p
        className={`rounded border px-2.5 py-2 font-mono text-[10.5px] ${
          mode === "live"
            ? "border-[var(--ip-green)]/40 text-[var(--ip-green)]"
            : "border-[var(--ip-grey-700)] text-neutral-500"
        }`}
      >
        {mode === "live"
          ? "OSPREY_MODE=live — findings come from the OSSPrey API."
          : "OSPREY_MODE=mock — findings are representative fixtures in the live API's exact shape. Set OSPREY_MODE=live and add credentials to switch; no other code changes."}
      </p>
    </div>
  );
}
