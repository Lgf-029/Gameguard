from app.graph.state import GameGuardState
from app.detectors.rule_engine import run_rule_engine
from app.detectors.vector_detect import run_vector_detect
from app.detectors.graph_detect import run_graph_detect


def rule_detect_node(state: GameGuardState) -> dict:
    result = run_rule_engine(state["uid"], state["device_id"], state["amount"])
    return {"rule_result": result}


def vector_detect_node(state: GameGuardState) -> dict:
    return {"vector_result": {"has_match": False, "similarity_score": 0.0, "top_matches": []}}
    result = run_vector_detect(
        state["uid"],
        state["device_id"],
        state["amount"],
        state["ip"],
        state["payment_method"],
    )
    return {"vector_result": result}


def graph_detect_node(state: GameGuardState) -> dict:
    result = run_graph_detect(state["uid"], state["device_id"])
    return {"graph_result": result}


def rrf_fusion_node(state: GameGuardState) -> dict:
    scores = []

    rule = state.get("rule_result") or {}
    if rule.get("player_exists"):
        scores.append(("rule", rule.get("total_score", 0)))

    vector = state.get("vector_result") or {}
    if vector.get("has_match"):
        sim = vector.get("similarity_score", 0)
        scores.append(("vector", sim * 50))

    graph = state.get("graph_result") or {}
    if graph.get("has_anomaly"):
        scores.append(("graph", graph.get("graph_score", 0)))

    if not scores:
        return {"risk_score": 0.0, "risk_level": "low", "action": "pass"}

    total = sum(s for _, s in scores) / len(scores)

    if total >= 80:
        level, action = "high", "block"
    elif total >= 40:
        level, action = "medium", "review"
    else:
        level, action = "low", "pass"

    return {
        "risk_score": round(total, 2),
        "risk_level": level,
        "action": action,
        "trace": {
            "rule_engine": rule,
            "vector_detect": vector,
            "graph_detect": graph,
        },
    }