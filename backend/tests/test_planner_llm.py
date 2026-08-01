"""Claude tool-use planner tests.

The planner cannot be exercised against the real API without a key, so these
drive the loop with a scripted fake client. They prove the parts that are ours:
tool dispatch, the assistant/tool_result message shape the API requires, event
emission, refusal handling, and the fallback path.

Once ANTHROPIC_API_KEY is set, `python verify_planner.py` runs the same
journey against the live API.
"""

from __future__ import annotations

import types

import pytest

from app.agent import events, planner_llm
from app.agent.tools import ToolContext


class _Block:
    """Stands in for an anthropic content block."""

    def __init__(self, type_: str, **kwargs):
        self.type = type_
        for key, value in kwargs.items():
            setattr(self, key, value)


class _Response:
    def __init__(self, stop_reason: str, content: list[_Block]):
        self.stop_reason = stop_reason
        self.content = content


class _FakeClient:
    """Replays a scripted list of responses and records what it was sent."""

    def __init__(self, script: list[_Response]):
        self._script = list(script)
        self.requests: list[dict] = []
        self.messages = types.SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        if not self._script:
            raise AssertionError("planner made more API calls than the script allows")
        return self._script.pop(0)


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Point the event bus at a scratch database."""
    import app.config as config
    import app.db as db

    db_path = tmp_path / "planner.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    from seed.seed import seed

    seed(reset=True)
    events._seq_counters.clear()

    # simulation_events has a foreign key to simulations; the real flow creates
    # that row in POST /api/simulate before the planner ever runs.
    with db.connect() as conn:
        for index in range(1, 8):
            conn.execute(
                "INSERT OR IGNORE INTO simulations (id, query, status, created_at) "
                "VALUES (?, 'test', 'planning', datetime('now'))",
                (f"sim_llm_{index}",),
            )
    yield


def _install(monkeypatch, client: _FakeClient) -> None:
    monkeypatch.setattr(planner_llm, "ANTHROPIC_API_KEY", "test-key")
    fake_module = types.SimpleNamespace(Anthropic=lambda api_key=None: client)
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake_module)


def test_agent_runs_tools_and_writes_events(monkeypatch):
    """A cascade investigation: two tool turns, then a final summary."""
    client = _FakeClient(
        [
            _Response(
                "tool_use",
                [
                    _Block(
                        "tool_use",
                        id="t1",
                        name="resolve_assets",
                        input={"query": "ransomware on the control centre"},
                    )
                ],
            ),
            _Response(
                "tool_use",
                [
                    _Block(
                        "tool_use",
                        id="t2",
                        name="run_cascade",
                        input={"seed_assets": ["control_centre"]},
                    )
                ],
            ),
            _Response(
                "end_turn",
                [_Block("text", text="Control Centre compromise reaches 6 assets.")],
            ),
        ]
    )
    _install(monkeypatch, client)

    ctx = ToolContext("sim_llm_1", "Simulate ransomware on the Control Centre")
    outcome = planner_llm.plan(ctx)

    assert outcome["summary"] == "Control Centre compromise reaches 6 assets."
    assert ctx.tools_used == ["resolve_assets", "run_cascade"]
    assert ctx.cascade_result["resilience_score_after"] == 43

    # The event stream is indistinguishable from the deterministic planner's.
    emitted = events.load_events("sim_llm_1")
    labels = [e["label"] for e in emitted]
    assert "Planning investigation" in labels
    assert "Calculating cascading impact" in labels
    assert emitted[-1]["type"] == "summary"
    assert all(e["status"] in {"done", "failed"} for e in emitted)


def test_conversation_shape_matches_api_contract(monkeypatch):
    """Assistant turn then a single user turn carrying every tool_result."""
    client = _FakeClient(
        [
            _Response(
                "tool_use",
                [
                    _Block("tool_use", id="a", name="graph_metrics", input={}),
                    _Block("tool_use", id="b", name="resolve_assets", input={"query": "hospital"}),
                ],
            ),
            _Response("end_turn", [_Block("text", text="Done.")]),
        ]
    )
    _install(monkeypatch, client)

    planner_llm.plan(ToolContext("sim_llm_2", "what is most central?"))

    second = client.requests[1]["messages"]
    assert second[0]["role"] == "user"
    assert second[1]["role"] == "assistant"
    # Both results must ride in ONE user message, or the model learns to stop
    # issuing parallel tool calls.
    assert second[2]["role"] == "user"
    results = second[2]["content"]
    assert len(results) == 2
    assert {r["tool_use_id"] for r in results} == {"a", "b"}
    assert all(r["type"] == "tool_result" for r in results)


def test_request_params_are_valid_for_the_model(monkeypatch):
    """Sonnet 5 rejects sampling params and manual thinking budgets."""
    client = _FakeClient([_Response("end_turn", [_Block("text", text="ok")])])
    _install(monkeypatch, client)
    planner_llm.plan(ToolContext("sim_llm_3", "hello"))

    request = client.requests[0]
    assert request["model"]
    assert request["max_tokens"] > 0
    assert {t["name"] for t in request["tools"]} == {
        "resolve_assets",
        "run_cascade",
        "graph_metrics",
        "get_inventory",
        "osprey_scan",
        "rank_mitigations",
    }
    for tool in request["tools"]:
        assert tool["input_schema"]["type"] == "object"
    # Removed on current models — sending any of these is a 400.
    for banned in ("temperature", "top_p", "top_k", "thinking"):
        assert banned not in request


def test_failing_tool_is_reported_and_run_continues(monkeypatch):
    """F7 AC#2: a failed tool renders as an error and the agent keeps going."""
    client = _FakeClient(
        [
            # rank_mitigations before any cascade -> the tool raises.
            _Response("tool_use", [_Block("tool_use", id="x", name="rank_mitigations", input={})]),
            _Response("end_turn", [_Block("text", text="Recovered without mitigations.")]),
        ]
    )
    _install(monkeypatch, client)

    outcome = planner_llm.plan(ToolContext("sim_llm_4", "rank mitigations"))
    assert outcome["summary"] == "Recovered without mitigations."

    failed = [e for e in events.load_events("sim_llm_4") if e["status"] == "failed"]
    assert failed and failed[0]["tool"] == "rank_mitigations"

    error_result = client.requests[1]["messages"][2]["content"][0]
    assert error_result["is_error"] is True


def test_refusal_falls_back_to_rule_planner(monkeypatch):
    """A safety refusal must not end the demo — the router takes over."""
    client = _FakeClient([_Response("refusal", [])])
    _install(monkeypatch, client)

    ctx = ToolContext("sim_llm_5", "Simulate ransomware on the Control Centre")
    outcome = planner_llm.plan(ctx)

    assert ctx.cascade_result is not None, "fallback should still produce a cascade"
    assert "Control Centre" in outcome["summary"]
    labels = [e["label"] for e in events.load_events("sim_llm_5")]
    assert "Switching to built-in planner" in labels


def test_no_key_uses_rule_planner(monkeypatch):
    monkeypatch.setattr(planner_llm, "ANTHROPIC_API_KEY", "")
    assert planner_llm.available() is False

    ctx = ToolContext("sim_llm_6", "What is our biggest single point of failure?")
    planner_llm.plan(ctx)
    # Structural question: metrics only, no cascade — same as the LLM path.
    assert ctx.tools_used == ["resolve_assets", "graph_metrics"]
