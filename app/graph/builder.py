from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.checkpoint.memory import MemorySaver
from app.graph.state import GameGuardState
from app.graph.nodes import (
    rule_detect_node,
    vector_detect_node,
    graph_detect_node,
    rrf_fusion_node,
    human_review_node,
    report_node,
)


def fanout_to_detectors(state: GameGuardState) -> list[Send]:
    return [
        Send("rule_detect", {
            "uid": state["uid"],
            "device_id": state["device_id"],
            "amount": state["amount"],
        }),
        Send("vector_detect", {
            "uid": state["uid"],
            "device_id": state["device_id"],
            "amount": state["amount"],
            "ip": state["ip"],
            "payment_method": state["payment_method"],
        }),
        Send("graph_detect", {
            "uid": state["uid"],
            "device_id": state["device_id"],
        }),
    ]


def route_after_fusion(state: GameGuardState) -> str:
    """根据风险等级路由：高风险直接报告，中风险人工审核，低风险直接报告"""
    action = state.get("action", "pass")
    if action == "review":
        return "human_review"
    return "report"


def build_graph():
    workflow = StateGraph(GameGuardState)

    workflow.add_node("rule_detect", rule_detect_node)
    workflow.add_node("vector_detect", vector_detect_node)
    workflow.add_node("graph_detect", graph_detect_node)
    workflow.add_node("fuse_rrf", rrf_fusion_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("report", report_node)

    workflow.add_conditional_edges(START, fanout_to_detectors)

    workflow.add_edge("rule_detect", "fuse_rrf")
    workflow.add_edge("vector_detect", "fuse_rrf")
    workflow.add_edge("graph_detect", "fuse_rrf")

    workflow.add_conditional_edges("fuse_rrf", route_after_fusion, {
        "human_review": "human_review",
        "report": "report",
    })

    workflow.add_edge("human_review", "report")
    workflow.add_edge("report", END)

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)