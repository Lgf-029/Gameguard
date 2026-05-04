from langgraph.graph import StateGraph, START, END
from app.graph.state import GameGuardState
from app.graph.nodes import (
    rule_detect_node,
    vector_detect_node,
    graph_detect_node,
    rrf_fusion_node,
)


def build_graph():
    workflow = StateGraph(GameGuardState)

    workflow.add_node("rule_detect", rule_detect_node)
    workflow.add_node("vector_detect", vector_detect_node)
    workflow.add_node("graph_detect", graph_detect_node)
    workflow.add_node("fuse_rrf", rrf_fusion_node)

    workflow.add_edge(START, "rule_detect")
    workflow.add_edge("rule_detect", "vector_detect")
    workflow.add_edge("vector_detect", "graph_detect")
    workflow.add_edge("graph_detect", "fuse_rrf")
    workflow.add_edge("fuse_rrf", END)

    return workflow.compile()