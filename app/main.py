from fastapi import FastAPI
from app.models.request import DetectRequest
from app.models.response import DetectResponse, TraceInfo, RuleResult, VectorResult, GraphResult
from app.graph.builder import build_graph
from app.databases.elasticsearch_client import ESClient
import datetime
from pydantic import BaseModel
from langgraph.types import Command

app = FastAPI(title="GameGuard")
graph = build_graph()

class ReviewDecision(BaseModel):
    transaction_id: str
    decision: str  # "approve" 或 "reject"
    feedback: str = ""


@app.post("/review")
def submit_review(decision: ReviewDecision) -> dict:
    config = {"configurable": {"thread_id": decision.transaction_id}}

    human_input = {
        "decision": decision.decision,
        "feedback": decision.feedback,
    }

    # 从断点恢复执行，传入审核员决定
    for event in graph.stream(Command(resume=human_input), config):
        pass

    final_state = graph.get_state(config).values

    return {
        "transaction_id": decision.transaction_id,
        "action": final_state.get("action", ""),
        "report": final_state.get("report", ""),
    }


@app.post("/detect", response_model=None)
def detect(req: DetectRequest):
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

    config = {"configurable": {"thread_id": req.transaction_id}}

    # 执行工作流，预期在 human_review_node 的 interrupt 处挂起
    try:
        graph.invoke(state, config)
    except:
        pass  # 中断时 invoke 会报错，忽略它

    # 读取挂起时的最新状态快照
    result = graph.get_state(config).values
    report_text = result.get("report", "")

    # 如果是审核挂起状态，手动填充提示信息
    if result.get("action") == "review" and not report_text:
        report_text = "交易已提交人工审核，请等待审核员处理。"

    trace = result.get("trace", {})
    rule = trace.get("rule_engine", {})
    vector = trace.get("vector_detect", {})
    graph_data = trace.get("graph_detect", {})

    es = ESClient()
    es.index_log("detection_logs", {
        "transaction_id": req.transaction_id,
        "uid": req.uid,
        "amount": float(req.amount),
        "device_id": req.device_id,
        "ip": req.ip,
        "payment_method": req.payment_method,
        "timestamp": datetime.datetime.now().isoformat(),
        "risk_score": result.get("risk_score", 0),
        "risk_level": result.get("risk_level", ""),
        "action": result.get("action", ""),
        "trace": result.get("trace", {}),
        "report": result.get("report", ""),
    })
    es.close()

    return DetectResponse(
        transaction_id=req.transaction_id,
        risk_score=result.get("risk_score", 0),
        risk_level=result.get("risk_level", ""),
        action=result.get("action", ""),
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
                "final_score": result.get("risk_score", 0),
                "sources": ["rule_engine", "vector_detect", "graph_detect"],
            },
        ),
        report=report_text,
        checkpoint_id="",
    )