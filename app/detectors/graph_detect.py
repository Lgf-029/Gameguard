from app.databases.neo4j_client import Neo4jClient

_neo4j = None

def _get_neo4j():
    global _neo4j
    if _neo4j is None:
        _neo4j = Neo4jClient()
    return _neo4j

def _check_device_farm(device_id: str) -> dict | None:
    rows = _get_neo4j().run_query(
        "MATCH (d:Device {device_id: $device_id})<-[:USED]-(p:Player) RETURN count(p) as account_count",
        {"device_id": device_id}
    )
    count = rows[0]["account_count"] if rows else 0
    if count >= 5:
        return {
            "type": "device_farm",
            "device_id": device_id,
            "account_count": count,
            "score": min(count * 12, 60)
        }
    return None

def _check_shared_device(player_id: str) -> list[dict]:
    rows = _get_neo4j().run_query(
        "MATCH (:Player {uid: $player_id})-[:USED]->(d:Device)<-[:USED]-(other:Player) "
        "WHERE other.uid <> $player_id "
        "RETURN d.device_id as device_id, count(DISTINCT other) as shared_count",
        {"player_id": player_id}
    )
    anomalies = []
    for row in rows:
        if row["shared_count"] >= 3:
            anomalies.append({
                "type": "shared_device",
                "device_id": row["device_id"],
                "account_count": row["shared_count"] + 1,
                "score": min(row["shared_count"] * 15, 45),
            })
    return anomalies

def run_graph_detect(player_id: str, device_id: str) -> dict:
    anomalies = []
    total_score = 0.0

    farm_result = _check_device_farm(device_id)
    if farm_result:
        anomalies.append(farm_result)
        total_score += farm_result["score"]

    shared_results = _check_shared_device(player_id)
    for r in shared_results:
        anomalies.append(r)
        total_score += r["score"]

    total_score = min(total_score, 100.0)

    return {
        "graph_score": total_score,
        "anomalies": anomalies,
        "has_anomaly": len(anomalies) > 0,
    }