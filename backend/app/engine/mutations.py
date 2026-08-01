"""Graph mutations for mitigation modelling (F5).

Every recommendation carries a `graph_mutation` -- a list of operations applied
to a *copy* of the graph so the engine can re-simulate and measure the real
resilience delta. Nothing here ever touches a live system; this is the
model-only guarantee stated in the UI banner.
"""

from __future__ import annotations

import copy
from typing import Any

SUPPORTED_OPS = {"add_edge", "remove_edge", "set_weight", "set_threshold", "set_status"}


class UnknownMutationOp(ValueError):
    pass


def apply_mutation(graph: dict[str, Any], mutation: dict[str, Any] | list[dict]) -> dict[str, Any]:
    """Return a new graph with `mutation` applied. Input graph is never modified."""
    operations = mutation.get("operations", []) if isinstance(mutation, dict) else list(mutation)
    result = copy.deepcopy(graph)

    for operation in operations:
        op = operation.get("op")
        if op not in SUPPORTED_OPS:
            raise UnknownMutationOp(f"Unsupported mutation op: {op!r}")

        if op == "add_edge":
            _remove_edge(result, operation)  # replace rather than duplicate
            result["dependencies"].append(
                {
                    "source": operation["source"],
                    "target": operation["target"],
                    "dependency_type": operation["dependency_type"],
                    "weight": float(operation["weight"]),
                }
            )
        elif op == "remove_edge":
            _remove_edge(result, operation)
        elif op == "set_weight":
            for dep in result["dependencies"]:
                if _matches(dep, operation):
                    dep["weight"] = float(operation["value"])
        elif op == "set_threshold":
            asset = result["assets"].get(operation["asset_id"])
            if asset is not None:
                asset["failure_threshold"] = float(operation["value"])
        elif op == "set_status":
            asset = result["assets"].get(operation["asset_id"])
            if asset is not None:
                asset["status"] = operation["value"]

    return result


def _matches(dep: dict[str, Any], operation: dict[str, Any]) -> bool:
    if dep["source"] != operation.get("source") or dep["target"] != operation.get("target"):
        return False
    wanted_type = operation.get("dependency_type")
    return wanted_type is None or dep["dependency_type"] == wanted_type


def _remove_edge(graph: dict[str, Any], operation: dict[str, Any]) -> None:
    graph["dependencies"] = [d for d in graph["dependencies"] if not _matches(d, operation)]
