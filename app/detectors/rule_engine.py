import json
import time
from typing import Optional
from app.databases.mysql_client import MySQLClient
from app.databases.redis_client import RedisClient

_mysql = None
_redis = None

def _get_mysql():
    global _mysql
    if _mysql is None:
        _mysql = MySQLClient()
    return _mysql

def _get_redis():
    global _redis
    if _redis is None:
        _redis = RedisClient()
    return _redis

# 常量
RULES_CACHE_KEY = "rule_engine:rules_meta"
RULES_CACHE_TTL = 600
PLAYER_CACHE_TTL = 300
DEVICE_CACHE_TTL = 300

# 规则加载
def load_rules() -> list[dict]:
    cache = _get_redis().get_cache(RULES_CACHE_KEY)
    if cache:
        return json.loads(cache)
    rows = _get_mysql().execute_query(
        "SELECT id, name, field, operator, threshold, score FROM rules WHERE enabled = 1"
    )
    rules = []
    for row in rows:
        rules.append({
            "id":row["id"],
            "name":row["name"],
            "field": row["field"],
            "operator": row["operator"],
            "threshold": float(row["threshold"]),
            "score": float(row["score"]),
        })
    _get_redis().set_cache(RULES_CACHE_KEY, json.dumps(rules), RULES_CACHE_TTL)
    return rules


# 玩家画像
def get_player_snapshot(player_id: str) -> Optional[dict]:
    cache_key = f"rule_engine:player_snapshot:{player_id}"
    cache = _get_redis().get_cache(cache_key)
    if cache:
        return json.loads(cache)
    rows = _get_mysql().execute_query(
        "SELECT uid, register_days, device_count, ip_count, total_recharge, total_orders FROM players WHERE uid = %s",
        (player_id,)
    )
    if not rows:
        return None
    player = dict(rows[0])
    _get_redis().set_cache(cache_key, json.dumps(player), PLAYER_CACHE_TTL)
    return player

# 设备信息
def get_device_info(device_id: str) -> Optional[dict]:
    cache_key = f"rule_engine:device_info:{device_id}"
    cache = _get_redis().get_cache(cache_key)
    if cache :
        return json.loads(cache)
    rows = _get_mysql().execute_query(
        "SELECT device_id,is_emulator,is_rooted,linked_account_count FROM devices WHERE device_id = %s",
        (device_id,)
    )
    if not rows:
        return None
    device = dict(rows[0])
    _get_redis().set_cache(cache_key,json.dumps(device),DEVICE_CACHE_TTL)
    return device

# 规则评估
def evaluate_rule(rule: dict, value: float) -> bool:
    op = rule["operator"]
    t = rule["threshold"]
    if op == "gt":
        return value > t
    elif op == "gte":
        return value >= t
    elif op == "lt":
        return value < t
    elif op == "lte":
        return value <= t
    elif op == "eq":
        return value == t
    return False

# 引擎入口
def run_rule_engine(player_id: str, device_id: str, amount: float) -> dict:
    rules = load_rules()

    player = get_player_snapshot(player_id)
    if not player:
        return {
            "player_id": player_id,
            "total_score": 0.0,
            "triggers": [],
            "player_exists": False,
            "high_freq_triggered": False,
        }

    device = get_device_info(device_id)
    if not device:
        device = {}

    window_key = f"uid:{player_id}:1h_recharge"
    _get_redis().add_event(window_key, str(time.time()))
    recharge_count_1h = _get_redis().sliding_window_count(window_key)

    lookup = {
        "register_days": player["register_days"],
        "amount": amount,
        "device_count": player.get("device_count", 0),
        "ip_count": player.get("ip_count", 0),
        "is_emulator": device.get("is_emulator", 0),
        "is_rooted": device.get("is_rooted", 0),
        "recharge_count_1h": recharge_count_1h,
    }

    triggers = []
    total_score = 0.0
    high_freq = recharge_count_1h >= 5

    for rule in rules:
        field = rule["field"]
        if field not in lookup:
            continue
        value = float(lookup[field])
        if evaluate_rule(rule, value):
            triggers.append({
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "field": field,
                "actual_value": value,
                "threshold": float(rule["threshold"]),
                "score": float(rule["score"]),
            })
            total_score += rule["score"]

    return {
        "player_id": player_id,
        "total_score": total_score,
        "triggers": triggers,
        "player_exists": True,
        "high_freq_triggered": high_freq,
    }