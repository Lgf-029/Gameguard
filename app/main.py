from fastapi import FastAPI
from app.models.request import DetectRequest
from app.models.response import DetectResponse, TraceInfo, RuleResult, VectorResult, GraphResult
from app.graph.builder import build_graph

app = FastAPI(title="GameGuard")
graph = build_graph()


@app.post("/detect")
def detect(req: DetectRequest) -> DetectResponse:
    state = {
        "transaction_id": req.transaction_id,
        "uid": req.uid,
        "amount": float(req.amount),
        "device_id": req.device_id,
        "ip": req.ip,
        "payment_method": req.payment_method,
        "rule_result": None,
        "vector_result": None,
        "graph_result": None,
        "risk_score": 0.0,
        "risk_level": "",
        "action": "",
        "trace": {},
        "error": "",
    }

    result = graph.invoke(state)

    trace = result.get("trace", {})
    rule = trace.get("rule_engine", {})
    vector = trace.get("vector_detect", {})
    graph_data = trace.get("graph_detect", {})

    return DetectResponse(
        transaction_id=req.transaction_id,
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
        action=result["action"],
        trace=TraceInfo(
            rule_engine=RuleResult(
                triggered_rules=[t.get("rule_name", "") for t in rule.get("triggers", [])],
                score=rule.get("total_score", 0.0),
            ),
            vector_detect=VectorResult(
                similar_transaction=vector.get("top_matches", [{}])[0].get("transaction_id", "") if vector.get("top_matches") else "",
                similarity=vector.get("similarity_score", 0.0),
            ),
            graph_detect=GraphResult(
                anomaly=graph_data.get("anomalies", [{}])[0].get("type", "") if graph_data.get("anomalies") else "",
                score=graph_data.get("graph_score", 0.0),
            ),
            rrf_fusion={
                "final_score": result["risk_score"],
                "sources": ["rule_engine", "vector_detect", "graph_detect"],
            },
        ),
        checkpoint_id="",
    )