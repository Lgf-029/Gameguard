from app.graph.state import GameGuardState
from app.detectors.rule_engine import run_rule_engine
from app.detectors.vector_detect import run_vector_detect
from app.detectors.graph_detect import run_graph_detect
from app.services.llm_client import get_llm
from langgraph.types import interrupt

def rule_detect_node(state: dict) -> dict:
    result = run_rule_engine(state["uid"], state["device_id"], state["amount"])
    return {"rule_result": result}


def vector_detect_node(state: GameGuardState) -> dict:
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


def rrf_rank(scores: list[tuple[str, float]], k: int = 60) -> dict:
    """按原始分数降序排名，返回每路的RRF分数"""
    ranked = sorted(scores, key=lambda x: x[1], reverse=True)
    result = {}
    for rank, (source, score) in enumerate(ranked, start=1):
        result[source] = 1.0 / (k + rank)
    return result


def rrf_fusion_node(state: GameGuardState) -> dict:
    rule = state.get("rule_result") or {}
    vector = state.get("vector_result") or {}
    graph = state.get("graph_result") or {}

    raw_scores = []

    if rule.get("player_exists"):
        raw_scores.append(("rule", rule.get("total_score", 0)))

    sim = vector.get("similarity_score", 0)
    if sim >= 0.2:
        vec_score = max(0.0, sim * 100)
        raw_scores.append(("vector", vec_score))

    if graph.get("has_anomaly"):
        raw_scores.append(("graph", graph.get("graph_score", 0)))

    if not raw_scores:
        return {"risk_score": 0.0, "risk_level": "low", "action": "pass"}

    rrf_scores = rrf_rank(raw_scores, k=60)

    # 赋予不同置信权重
    weights = {"rule": 0.4, "vector": 0.35, "graph": 0.25}
    total_rrf = sum(rrf_scores.get(src, 0) * weights.get(src, 0.3) for src, _ in raw_scores)

    # 归一化
    max_possible = sum(weights.values()) * (1.0 / (60 + 1))
    normalized = (total_rrf / max_possible) * 100 if max_possible > 0 else 0.0

    if normalized >= 80:
        level, action = "high", "block"
    elif normalized >= 40:
        level, action = "medium", "review"
    else:
        level, action = "low", "pass"

    return {
        "risk_score": round(normalized, 2),
        "risk_level": level,
        "action": action,
        "trace": {
            "rule_engine": rule,
            "vector_detect": vector,
            "graph_detect": graph,
        },
        "fusion_method": "rrf_weighted"
    }

def report_node(state: GameGuardState) -> dict:
    """根据检测结果生成自然语言风控报告"""
    trace = state.get("trace", {})
    llm = get_llm(temperature=0.1)

    prompt = f"""根据以下风控检测结果，用中文生成一份简洁的风控报告：

规则引擎检测：{trace.get("rule_engine", {})}
向量相似度检测：{trace.get("vector_detect", {})}
知识图谱检测：{trace.get("graph_detect", {})}
最终风险分：{state.get("risk_score", 0)}
风险等级：{state.get("risk_level", "unknown")}
处置建议：{state.get("action", "unknown")}

请用专业、简洁的语言，说明每路检测发现了什么、最终结论是什么。"""

    report = llm.invoke(prompt).content
    return {"report": report}


def human_review_node(state: GameGuardState) -> dict:
    """中风险交易推人工审核，先生成报告再提交审核"""
    trace = state.get("trace", {})
    llm = get_llm(temperature=0.1)

    # 先生成报告
    report_prompt = f"""根据以下风控检测结果，用中文生成一份详细的风险分析报告：

规则引擎检测：{trace.get("rule_engine", {})}
向量相似度检测：{trace.get("vector_detect", {})}
知识图谱检测：{trace.get("graph_detect", {})}
最终风险分：{state.get("risk_score", 0)}
风险等级：{state.get("risk_level", "unknown")}
处置建议：{state.get("action", "unknown")}

请用专业、简洁的语言，说明每路检测发现了什么风险、最终的综合风险判断是什么。"""

    analysis_report = llm.invoke(report_prompt).content

    # 把报告和交易信息一起提交给审核员
    review_payload = {
        "transaction_id": state.get("transaction_id", ""),
        "uid": state.get("uid", ""),
        "amount": state.get("amount", 0),
        "risk_score": state.get("risk_score", 0),
        "trace": state.get("trace", {}),
        "analysis_report": analysis_report,
        "message": "请审核员根据以上风险分析报告做出决定：approve（通过）/ reject（拒绝）",
    }

    human_input = interrupt(review_payload)
    decision = human_input.get("decision", "reject")
    feedback = human_input.get("feedback", "")

    if decision == "approve":
        return {
            "action": "pass",
            "report": f"人工审核通过。审核员反馈：{feedback}\n\n系统分析报告：{analysis_report}",
        }
    else:
        return {
            "action": "block",
            "report": f"人工审核拒绝。审核员反馈：{feedback}\n\n系统分析报告：{analysis_report}",
        }