"""OSSPrey supply chain layer (F6).

OSSPrey's angle is behavioural detection of malicious open source packages
rather than CVE lookup, so findings describe *intent* ("executes conditional
filesystem writes at install time"), not a CVSS vector.

InfraPilot's contribution is re-ranking those findings by operational impact:

    impact = severity_weight x downstream_criticality(asset)

where downstream_criticality is measured by running the cascade from that asset.
The same flagged package therefore outranks itself on the Control Centre versus
the Data Centre, because the Control Centre's cascade reaches the Hospital.
"""

from __future__ import annotations

from typing import Any

from ..config import OSPREY_MODE
from ..db import connect
from ..engine.cascade import run_cascade
from ..engine.metrics import downstream_criticality
from seed.seed_data import SEVERITY_WEIGHT


def mode() -> str:
    return OSPREY_MODE if OSPREY_MODE in {"mock", "live"} else "mock"


def _impact_chain(graph: dict, asset_id: str) -> list[str]:
    """The dependency chain from the flagged asset to its worst consequence."""
    if asset_id not in graph["assets"]:
        return []
    result = run_cascade(graph, [asset_id])
    path = result["critical_path"]

    # Prefer a chain that ends on the highest-criticality impacted asset --
    # that is the sentence the operator actually needs to hear.
    impacted = [a for a in result["newly_impacted"] if a != asset_id]
    if impacted:
        worst = max(impacted, key=lambda a: (graph["assets"][a]["criticality"], a))
        if worst not in path:
            path = path + [worst]
    return path


def scan_asset(graph: dict, asset_id: str) -> list[dict[str, Any]]:
    """Findings for one asset, enriched with operational impact and chain."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM supply_chain_findings WHERE asset_id = ? ORDER BY id",
            (asset_id,),
        ).fetchall()

    reach = downstream_criticality(graph, asset_id)
    chain = _impact_chain(graph, asset_id)
    findings = []

    names = {aid: asset["name"] for aid, asset in graph["assets"].items()}
    reaches = [names.get(node, node) for node in chain[1:]] or ["no downstream assets"]

    for row in rows:
        weight = SEVERITY_WEIGHT.get(row["severity"], 0.3)
        impact = round(weight * reach, 2)
        findings.append(
            {
                "id": row["id"],
                "asset_id": row["asset_id"],
                "asset_name": names.get(asset_id, asset_id),
                "package": row["package"],
                "severity": row["severity"],
                "behaviour": row["behaviour"],
                "operational_impact": impact,
                "downstream_criticality": reach,
                "severity_weight": weight,
                # Spelled out so the ranking is auditable rather than a black box.
                "rank_reason": (
                    f"{row['severity']} severity (x{weight}) on an asset whose failure "
                    f"reaches {', '.join(reaches)} — downstream criticality {reach}."
                ),
                "chain": chain,
                "chain_names": [names.get(node, node) for node in chain],
            }
        )

    _persist(findings)
    return findings


def scan_all(graph: dict) -> list[dict[str, Any]]:
    """Every finding across the city, ranked by operational impact (F6 AC#2)."""
    with connect() as conn:
        asset_ids = [
            row["asset_id"]
            for row in conn.execute(
                "SELECT DISTINCT asset_id FROM supply_chain_findings ORDER BY asset_id"
            )
        ]

    findings: list[dict[str, Any]] = []
    for asset_id in asset_ids:
        findings.extend(scan_asset(graph, asset_id))

    findings.sort(
        key=lambda f: (-f["operational_impact"], f["asset_id"], f["package"])
    )
    return findings


def impact_comparison(graph: dict) -> dict[str, Any] | None:
    """Two equally-severe findings that InfraPilot ranks differently.

    This is the argument for the whole layer: CVSS-style severity says these
    are the same problem, operational impact says they are not, because one
    asset's failure reaches acute healthcare and the other's does not.
    """
    findings = scan_all(graph)
    by_severity: dict[str, list[dict]] = {}
    for finding in findings:
        by_severity.setdefault(finding["severity"], []).append(finding)

    for severity in ("high", "medium", "low"):
        peers = by_severity.get(severity, [])
        if len(peers) < 2:
            continue
        higher, lower = peers[0], peers[-1]
        if higher["operational_impact"] <= lower["operational_impact"]:
            continue
        ratio = round(higher["operational_impact"] / max(lower["operational_impact"], 0.01), 1)
        return {
            "severity": severity,
            "higher": higher,
            "lower": lower,
            "ratio": ratio,
            "explanation": (
                f"OSSPrey flags both as {severity} severity — by behaviour, they are "
                f"the same class of threat. InfraPilot ranks {higher['package']} on "
                f"{higher['asset_name']} {ratio}x higher because that asset's failure "
                f"cascades to {', '.join(higher['chain_names'][1:]) or 'other assets'}, "
                f"while {lower['asset_name']} does not. Patch order should follow "
                f"operational impact, not severity alone."
            ),
        }
    return None


def _persist(findings: list[dict[str, Any]]) -> None:
    import json

    with connect() as conn:
        for finding in findings:
            conn.execute(
                "UPDATE supply_chain_findings SET operational_impact = ?, chain = ? WHERE id = ?",
                (finding["operational_impact"], json.dumps(finding["chain"]), finding["id"]),
            )


def findings_summary(graph: dict, asset_id: str) -> dict[str, Any]:
    """Compact badge payload for the node detail sheet (F6 AC#1)."""
    findings = scan_asset(graph, asset_id)
    if not findings:
        return {"count": 0, "top_severity": None, "findings": []}
    order = {"high": 3, "medium": 2, "low": 1}
    top = max(findings, key=lambda f: order.get(f["severity"], 0))
    return {
        "count": len(findings),
        "top_severity": top["severity"],
        "findings": findings,
    }
