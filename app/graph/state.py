from typing import TypedDict


class GameGuardState(TypedDict):
    transaction_id: str
    uid: str
    amount: float
    device_id: str
    ip: str
    payment_method: str
    rule_result: dict | None
    vector_result: dict | None
    graph_result: dict | None
    risk_score: float
    risk_level: str
    action: str
    trace: dict
    error: str