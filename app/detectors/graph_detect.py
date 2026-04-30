import json
from typing import Optional
from app.databases.neo4j_client import Neo4jClient

_neo4j = None

def _get_neo4j():
    global _neo4j
    if _neo4j is None:
        _neo4j = Neo4jClient()
    return _neo4j

def check_device_farm(device_id: str) -> Optional[dict]:
    pass

def check_shared_device(player_id: str) -> list[dict]:
    pass

def run_graph_detect(player_id: str, device_id: str) -> dict:
    pass
