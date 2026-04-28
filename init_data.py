import random
from datetime import datetime
from faker import Faker
from app.databases.mysql_client import MySQLClient
from app.databases.redis_client import RedisClient
from app.databases.elasticsearch_client import ESClient
from app.databases.milvus_client import MilvusClientWrapper
from app.databases.neo4j_client import Neo4jClient
from app.services.embedding_client import get_embedding

fake = Faker(['zh_CN'])
Faker.seed(42)
random.seed(42)

mysql = MySQLClient()
redis = RedisClient()
es = ESClient()
milvus = MilvusClientWrapper()
neo4j = Neo4jClient()

# ── 建表（每次重建保证结构一致）──
mysql.execute_update("DROP TABLE IF EXISTS transactions")
mysql.execute_update("DROP TABLE IF EXISTS devices")
mysql.execute_update("DROP TABLE IF EXISTS players")
mysql.execute_update("DROP TABLE IF EXISTS rules")

mysql.execute_update("""
    CREATE TABLE players (
        uid VARCHAR(50) PRIMARY KEY,
        name VARCHAR(100),
        registered_at DATETIME,
        risk_label VARCHAR(20) DEFAULT 'normal',
        total_recharge DECIMAL(12, 2) DEFAULT 0.00,
        total_orders INT DEFAULT 0,
        register_days INT DEFAULT 0,
        device_count INT DEFAULT 0,
        ip_count INT DEFAULT 0
    )
""")

mysql.execute_update("""
    CREATE TABLE devices (
        device_id VARCHAR(50) PRIMARY KEY,
        is_emulator TINYINT DEFAULT 0,
        is_rooted TINYINT DEFAULT 0,
        linked_account_count INT DEFAULT 0
    )
""")

mysql.execute_update("""
    CREATE TABLE transactions (
        transaction_id VARCHAR(50) PRIMARY KEY,
        uid VARCHAR(50),
        amount DECIMAL(10, 2),
        device_id VARCHAR(50),
        ip VARCHAR(20),
        payment_method VARCHAR(20),
        timestamp DATETIME,
        risk_label VARCHAR(20) DEFAULT 'normal'
    )
""")

mysql.execute_update("""
    CREATE TABLE rules (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        field VARCHAR(50) NOT NULL,
        operator VARCHAR(10) NOT NULL,
        threshold DECIMAL(15, 4) NOT NULL,
        score DECIMAL(5, 2) NOT NULL,
        enabled TINYINT DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )
""")
mysql.execute_update("DELETE FROM rules")

# ── 1. 玩家账号 (200个) ──
print("生成玩家账号...")
players_raw = []
now = datetime.now()
for i in range(180):
    uid = f"player_{i+1:03d}"
    registered_at = fake.date_time_between(start_date="-2y", end_date="-1y")
    register_days = (now - registered_at).days
    players_raw.append({
        "uid": uid,
        "name": fake.name(),
        "registered_at": registered_at.strftime("%Y-%m-%d %H:%M:%S"),
        "risk_label": "normal",
        "register_days": register_days,
    })

for i in range(20):
    uid = f"player_fraud_{i+1:02d}"
    registered_at = fake.date_time_between(start_date="-30d", end_date="now")
    register_days = max((now - registered_at).days, 1)
    players_raw.append({
        "uid": uid,
        "name": fake.name(),
        "registered_at": registered_at.strftime("%Y-%m-%d %H:%M:%S"),
        "risk_label": "fraud",
        "register_days": register_days,
    })

player_ids = [p["uid"] for p in players_raw]
fraud_uids = [p["uid"] for p in players_raw if p["risk_label"] == "fraud"]

# ── 2. 设备指纹 (100个) ──
print("生成设备指纹...")
devices_raw = []
for i in range(100):
    device_id = f"dev_{i+1:03d}"
    is_emulator = 1 if random.random() < 0.10 else 0
    is_rooted = 1 if random.random() < 0.15 else 0
    devices_raw.append({
        "device_id": device_id,
        "is_emulator": is_emulator,
        "is_rooted": is_rooted,
    })

device_ids = [d["device_id"] for d in devices_raw]

# ── 3. 交易记录 (300条) ──
print("生成交易记录...")
payment_methods = ["wechat", "alipay", "apple_pay", "credit_card"]
ip_pools = [f"192.168.{i}.{j}" for i in range(1, 6) for j in range(1, 51)]
fraud_ip_pools = [f"10.0.{i}.{j}" for i in range(1, 4) for j in range(1, 20)]

transactions = []

# 3.1 正常交易 290 条
for i in range(290):
    txn_id = f"txn_{i+1:04d}"
    uid = random.choice([p for p in player_ids if p not in fraud_uids])
    device_id = random.choice(device_ids)
    ip = random.choice(ip_pools)
    t = fake.date_time_between(start_date="-90d", end_date="now")
    amount = round(random.uniform(1, 500), 2)
    if random.random() < 0.05:
        amount = round(random.uniform(500, 2000), 2)
    transactions.append({
        "transaction_id": txn_id,
        "uid": uid,
        "amount": amount,
        "device_id": device_id,
        "ip": ip,
        "payment_method": random.choice(payment_methods),
        "timestamp": t.strftime("%Y-%m-%d %H:%M:%S"),
        "risk_label": "normal",
    })

# 3.2 混入 10 条异常交易
anomaly_profiles = [
    {"amount_range": (648, 648), "ip_pool": fraud_ip_pools, "desc": "新注册大额648"},
    {"amount_range": (500, 5000), "ip_pool": ip_pools, "desc": "大额异常"},
    {"amount_range": (1, 100), "ip_pool": fraud_ip_pools, "desc": "高频小额"},
]
for i in range(10):
    txn_id = f"txn_{290+i+1:04d}"
    uid = random.choice(fraud_uids)
    profile = random.choice(anomaly_profiles)
    device_id = random.choice(device_ids)
    ip = random.choice(profile["ip_pool"])
    t = fake.date_time_between(start_date="-7d", end_date="now")
    amount = round(random.uniform(*profile["amount_range"]), 2)
    transactions.append({
        "transaction_id": txn_id,
        "uid": uid,
        "amount": amount,
        "device_id": device_id,
        "ip": ip,
        "payment_method": random.choice(payment_methods),
        "timestamp": t.strftime("%Y-%m-%d %H:%M:%S"),
        "risk_label": "fraud",
    })

# ── 4. 回写玩家聚合指标 ──
print("计算玩家聚合指标...")
player_stats = {uid: {"total_recharge": 0.0, "total_orders": 0, "devices": set(), "ips": set()} for uid in player_ids}
for txn in transactions:
    uid = txn["uid"]
    player_stats[uid]["total_recharge"] += txn["amount"]
    player_stats[uid]["total_orders"] += 1
    player_stats[uid]["devices"].add(txn["device_id"])
    player_stats[uid]["ips"].add(txn["ip"])

for p in players_raw:
    stats = player_stats[p["uid"]]
    p["total_recharge"] = round(stats["total_recharge"], 2)
    p["total_orders"] = stats["total_orders"]
    p["device_count"] = len(stats["devices"])
    p["ip_count"] = len(stats["ips"])

mysql.execute_insert_many(
    "INSERT INTO players (uid, name, registered_at, risk_label, total_recharge, total_orders, register_days, device_count, ip_count) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
    [
        (p["uid"], p["name"], p["registered_at"], p["risk_label"],
         p["total_recharge"], p["total_orders"], p["register_days"],
         p["device_count"], p["ip_count"])
        for p in players_raw
    ]
)
print(f"  玩家账号: {len(players_raw)} 条 (180 normal + 20 fraud)")

# ── 5. 回写设备聚合指标 ──
device_txn_count = {d: 0 for d in device_ids}
device_player_set = {d: set() for d in device_ids}
for txn in transactions:
    device_txn_count[txn["device_id"]] += 1
    device_player_set[txn["device_id"]].add(txn["uid"])

for d in devices_raw:
    d["linked_account_count"] = len(device_player_set[d["device_id"]])

# 强制 dev_099 关联 5 个 fraud 账号
dev_099 = next(d for d in devices_raw if d["device_id"] == "dev_099")
dev_099["linked_account_count"] = max(dev_099["linked_account_count"], 5)

mysql.execute_insert_many(
    "INSERT INTO devices (device_id, is_emulator, is_rooted, linked_account_count) VALUES (%s, %s, %s, %s)",
    [(d["device_id"], d["is_emulator"], d["is_rooted"], d["linked_account_count"]) for d in devices_raw]
)
print(f"  设备指纹: {len(devices_raw)} 条")

# ── 6. 写入交易表 ──
mysql.execute_insert_many(
    "INSERT INTO transactions (transaction_id, uid, amount, device_id, ip, payment_method, timestamp, risk_label) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
    [
        (t["transaction_id"], t["uid"], t["amount"], t["device_id"], t["ip"],
         t["payment_method"], t["timestamp"], t["risk_label"])
        for t in transactions
    ]
)
print(f"  交易记录: {len(transactions)} 条 (290 normal + 10 fraud)")

# ── 7. 规则种子数据 ──
print("写入风控规则...")
seed_rules = [
    ("新注册大额充值",     "register_days",     "lte", 7.0,   50.0),
    ("单笔超过648",        "amount",            "gte", 648.0, 40.0),
    ("同设备多账号",       "device_count",      "gte", 5.0,   60.0),
    ("1小时内高频充值",    "recharge_count_1h", "gte", 5.0,   30.0),
    ("设备为模拟器",       "is_emulator",       "eq",  1.0,   35.0),
    ("设备已ROOT",         "is_rooted",         "eq",  1.0,   25.0),
    ("IP关联多账号",       "ip_count",          "gte", 3.0,   20.0),
    ("支付失败次数异常",   "payment_fail_count","gte", 5.0,   15.0),
]
mysql.execute_insert_many(
    "INSERT INTO rules (name, field, operator, threshold, score) VALUES (%s, %s, %s, %s, %s)",
    seed_rules
)
print(f"  规则写入: {len(seed_rules)} 条")

# ── 8. Milvus 异常模式向量 ──
print("生成异常模式Embedding...")
anomaly_patterns = [
    "新注册账号24小时内单笔充值超过648元",
    "同设备关联超过5个账号",
    "1小时内充值超过10次",
    "异地登录后立即修改密码并大额转账",
    "客户端上报数据异常，疑似外挂加速",
    "多账号同IP固定操作间隔，疑似脚本",
    "充值后短时间内申请退款",
    "同一支付方式关联多个高危账号",
    "设备模拟器环境，批量注册小号",
    "凌晨时段高频小额充值",
    "账号被盗后异地大额消费",
    "玩家间交易异常，疑似洗钱环",
    "IP段关联多个退款申请",
    "设备ROOT后修改充值参数",
    "新设备异常高频切换账号",
    "充值金额与历史行为模式突变",
    "同设备多账号轮换登录",
    "支付失败次数异常偏高",
    "短时间内跨多地区IP登录",
    "长期静默账号突然大额充值后提现",
    "同IP下多账号集中时段交易",
    "虚拟商品购买后立即转售",
    "账号实名信息与支付账户不一致",
    "新注册账号批量添加好友后发广告",
    "交易金额精准卡在风控阈值以下",
]

milvus.create_collection("anomaly_patterns", 1024)
pattern_ids = []
pattern_vectors = []
for i, text in enumerate(anomaly_patterns):
    vec = get_embedding(text)
    pattern_ids.append(f"pattern_{i+1:02d}")
    pattern_vectors.append(vec)
milvus.insert_vectors("anomaly_patterns", pattern_vectors, pattern_ids)
print(f"  异常模式向量写入Milvus: {len(anomaly_patterns)} 条")

# ── 9. Milvus 交易行为向量 ──
print("生成交易行为向量...")
milvus.create_collection("transaction_behaviors", 1024)
fraud_txns = [t for t in transactions if t["risk_label"] == "fraud"]
txn_ids = []
txn_vectors = []
for txn in fraud_txns:
    text = f"uid:{txn['uid']} amount:{txn['amount']} device:{txn['device_id']} ip:{txn['ip']} payment:{txn['payment_method']}"
    vec = get_embedding(text)
    txn_ids.append(txn["transaction_id"])
    txn_vectors.append(vec)
milvus.insert_vectors("transaction_behaviors", txn_vectors, txn_ids)
print(f"  交易行为向量写入Milvus: {len(fraud_txns)} 条")

# ── 10. Neo4j 图关系 ──
print("构建Neo4j图关系...")
neo4j.run_query("MATCH (n) DETACH DELETE n")
for p in players_raw:
    neo4j.run_query(
        "CREATE (:Player {uid: $uid, name: $name, risk_label: $risk_label})",
        {"uid": p["uid"], "name": p["name"], "risk_label": p["risk_label"]}
    )
for d in devices_raw:
    neo4j.run_query(
        "CREATE (:Device {device_id: $device_id, is_emulator: $is_emulator, is_rooted: $is_rooted})",
        {"device_id": d["device_id"], "is_emulator": d["is_emulator"], "is_rooted": d["is_rooted"]}
    )

sampled_txns = random.sample(transactions, min(120, len(transactions)))
for txn in sampled_txns:
    try:
        neo4j.run_query("""
            MATCH (p:Player {uid: $uid})
            MATCH (d:Device {device_id: $device_id})
            MERGE (p)-[:USED]->(d)
        """, {"uid": txn["uid"], "device_id": txn["device_id"]})
    except Exception:
        pass

for uid in fraud_uids[:5]:
    try:
        neo4j.run_query("""
            MATCH (p:Player {uid: $uid})
            MATCH (d:Device {device_id: $device_id})
            MERGE (p)-[:USED]->(d)
        """, {"uid": uid, "device_id": "dev_099"})
    except Exception:
        pass

print(f"  Neo4j图关系构建完成")

# ── 11. ES 日志 ──
print("写入ES日志...")
for txn in transactions[:50]:
    doc = {
        "transaction_id": txn["transaction_id"],
        "uid": txn["uid"],
        "amount": float(txn["amount"]),
        "device_id": txn["device_id"],
        "ip": txn["ip"],
        "payment_method": txn["payment_method"],
        "timestamp": txn["timestamp"],
        "risk_label": txn["risk_label"],
    }
    es.index_log("transaction_logs", doc)
print(f"  ES日志: 50 条")

# ── 12. 汇总 ──
print("\n========== 数据初始化完成 ==========")
print(f"  MySQL players:       {len(players_raw)} 条")
print(f"  MySQL devices:       {len(devices_raw)} 条")
print(f"  MySQL transactions:  {len(transactions)} 条")
print(f"  MySQL rules:         {len(seed_rules)} 条")
print(f"  Milvus patterns:     {len(anomaly_patterns)} 条")
print(f"  Milvus behaviors:    {len(fraud_txns)} 条")
print(f"  Neo4j nodes:         约{len(players_raw) + len(devices_raw)} 个")
print(f"  ES logs:             50 条")
print("======================================")

mysql.close()
redis.close()
es.close()
milvus.close()
neo4j.close()