from __future__ import annotations

from typing import Any, TypedDict

from app.agents.pipeline import run_pipeline


class GraphState(TypedDict, total=False):
    symbol: str
    user_id: str
    simulate_failure: str | None
    result: dict[str, Any]


def compile_graph():
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return None

    def node_run(state: GraphState) -> GraphState:
        result = run_pipeline(
            state["symbol"],
            state.get("user_id") or "local",
            state.get("simulate_failure"),
        )
        return {**state, "result": result}

    g = StateGraph(GraphState)
    g.add_node("orchestrator", node_run)
    g.set_entry_point("orchestrator")
    g.add_edge("orchestrator", END)
    return g.compile()


graph_app = compile_graph()
