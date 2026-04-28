import json
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

# ── 常量 ──
RULES_CACHE_KEY = "rule_engine:rules_meta"
RULES_CACHE_TTL = 600
PLAYER_CACHE_TTL = 300
DEVICE_CACHE_TTL = 300

# ── 规则加载 ──
def load_rules() -> list[dict]:
    # 1. 查 Redis 缓存，命中则 json.loads 返回
    # 2. 未命中 → execute_query("SELECT id, name, field, operator, threshold, score FROM rules WHERE enabled = 1")
    # 3. 遍历结果，转成 list[dict]，threshold 和 score 用 float() 强转
    # 4. json.dumps 写入 Redis，TTL=RULES_CACHE_TTL
    # 5. 返回 list[dict]

# ── 玩家画像 ──
def get_player_snapshot(player_id: str) -> Optional[dict]:
    # 1. cache_key = f"rule_engine:player_snapshot:{player_id}"
    # 2. 查 Redis，命中 → json.loads 返回
    # 3. execute_query("SELECT uid, register_days, device_count, ip_count, total_recharge, total_orders FROM players WHERE uid = %s", (player_id,))
    # 4. 无结果返回 None
    # 5. player = dict(rows[0])
    # 6. json.dumps 写入 Redis，TTL=PLAYER_CACHE_TTL
    # 7. 返回 player

# ── 设备信息 ──
def get_device_info(device_id: str) -> Optional[dict]:
    # 1. cache_key = f"rule_engine:device_info:{device_id}"
    # 2. 查 Redis，命中 → json.loads 返回
    # 3. execute_query("SELECT device_id, is_emulator, is_rooted FROM devices WHERE device_id = %s", (device_id,))
    # 4. 无结果返回 None
    # 5. device = dict(rows[0])
    # 6. json.dumps 写入 Redis，TTL=DEVICE_CACHE_TTL
    # 7. 返回 device

# ── 规则评估 ──
def evaluate_rule(rule: dict, value: float) -> bool:
    # op = rule["operator"]
    # t = rule["threshold"]
    # if op == "gt":  return value > t
    # elif op == "gte": return value >= t
    # elif op == "lt":  return value < t
    # elif op == "lte": return value <= t
    # elif op == "eq":  return value == t
    # return False

# ── 引擎入口 ──
def run_rule_engine(player_id: str, device_id: str, amount: float) -> dict:
    # 返回值结构定死：
    # {
    #     "player_id": str,
    #     "total_score": float,
    #     "triggers": [
    #         {
    #             "rule_id": int,
    #             "rule_name": str,
    #             "field": str,
    #             "actual_value": float,
    #             "threshold": float,
    #             "score": float,
    #         }
    #     ],
    #     "player_exists": bool,
    #     "high_freq_triggered": bool,
    # }

    # 流程：
    # 1. load_rules()
    # 2. get_player_snapshot(player_id)，如果 None → 直接返回 player_exists=False, total_score=0, triggers=[]
    # 3. get_device_info(device_id)，如果 None → device_info = {}（允许设备不存在，不阻断检测）
    # 4. 合并数据源：player_dict 和 device_info 合并成一个 lookup dict，再加入 amount 作为虚拟字段
    #    lookup = {**player, **device_info, "amount": amount}
    # 4.5. 插入 Redis 滑动窗口事件
    #    window_key = f"rule_engine:recharge_window:{player_id}"
    #    add_event(window_key, score=1)   ← 注意你 redis_client.add_event 签名是 (key, value)，这里传 value="1" 或 str(time.time())
    #    然后 lookup["recharge_count_1h"] = sliding_window_count(window_key, window_seconds=3600)
    # 5. 遍历 rules，对每条 rule：
    #    field = rule["field"]
    #    if field not in lookup: continue
    #    value = float(lookup[field])
    #    if evaluate_rule(rule, value):
    #        triggers.append({...})
    #        total_score += rule["score"]
    # 6. 判断 high_freq_triggered：recharge_count_1h >= 5（或者用 "HIGH_FREQ_RECHARGE" 是否在 triggers 中判断）
    # 7. return dict