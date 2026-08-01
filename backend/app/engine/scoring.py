"""Resilience scoring.

score = 100 * (1 - Sigma(criticality_i * impact_i) / Sigma(criticality_i))

where impact is 1.0 for a failed asset and 0.5 for a degraded one. Rounded to
an integer. An all-healthy city scores 100; the seed city scores lower because
it carries real posture debt (see docs/SCORING.md).
"""

from __future__ import annotations

IMPACT_WEIGHT = {"failed": 1.0, "degraded": 0.5, "healthy": 0.0, "hardened": 0.0}


def impact_penalty(assets: dict[str, dict], statuses: dict[str, str]) -> float:
    """Weighted criticality lost across the city."""
    return sum(
        asset["criticality"] * IMPACT_WEIGHT.get(statuses.get(asset_id, "healthy"), 0.0)
        for asset_id, asset in assets.items()
    )


def resilience_score(assets: dict[str, dict], statuses: dict[str, str]) -> int:
    """Integer 0..100. Higher is more resilient."""
    total_criticality = sum(asset["criticality"] for asset in assets.values())
    if total_criticality == 0:
        return 100
    penalty = impact_penalty(assets, statuses)
    return round(100 * (1 - penalty / total_criticality))
