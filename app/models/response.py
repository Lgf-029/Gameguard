from pydantic import BaseModel
from typing import Optional


class RuleResult(BaseModel):
    triggered_rules: list[str] = []
    score: float = 0.0


class VectorResult(BaseModel):
    similar_behavior: Optional[str] = None
    similarity: float = 0.0


class GraphResult(BaseModel):
    anomaly: Optional[str] = None
    score: float = 0.0


class TraceInfo(BaseModel):
    rule_engine: RuleResult = RuleResult()
    vector_detect: VectorResult = VectorResult()
    graph_detect: GraphResult = GraphResult()
    rrf_fusion: dict = {}


class DetectResponse(BaseModel):
    transaction_id: str
    risk_score: float
    risk_level: str  # "high" / "medium" / "low"
    action: str  # "block" / "review" / "pass"
    trace: TraceInfo
    report: str = ""
    checkpoint_id: Optional[str] = None