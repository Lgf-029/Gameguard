from app.databases.mysql_client import MySQLClient
from app.databases.redis_client import RedisClient
from app.detectors.rule_engine import run_rule_engine
from app.detectors.vector_detect import run_vector_detect
from app.detectors.graph_detect import run_graph_detect
from app.graph.nodes import rrf_fusion_node

def clear_redis():
    """清除redis数据库，保证三次实验互不影响"""
    r = RedisClient()
    r.client.flushall()
    r.close()

def load_all_transactions():
    """加载全部300条交易作为测试集（290正常 + 10异常）"""
    mysql = MySQLClient()
    rows = mysql.execute_query(
        "SELECT transaction_id, uid, amount, device_id, ip, payment_method, risk_label "
        "FROM transactions"
    )
    mysql.close()
    return rows

def run_experiment_1_rule_only(test_txns):
    """实验一：规则引擎"""
    clear_redis()
    scores = []
    for txn in test_txns:
        state = {
            "rule_result": run_rule_engine(txn["uid"], txn["device_id"], float(txn["amount"])),
            "vector_result": {},
            "graph_result": {},
        }
        result = rrf_fusion_node(state)
        scores.append((
            txn["transaction_id"],
            result["risk_score"],
            result["action"],
            txn["risk_label"]
        ))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores

def run_experiment_2_rule_and_vector(test_txns):
    """实验二：规则引擎+向量检测"""
    clear_redis()
    scores = []
    for txn in test_txns:
        state = {
            "rule_result": run_rule_engine(txn["uid"], txn["device_id"], float(txn["amount"])),
            "vector_result": run_vector_detect(
                txn["uid"], txn["device_id"], float(txn["amount"]),
                txn["ip"], txn["payment_method"]
            ),
            "graph_result": {},
        }
        result = rrf_fusion_node(state)
        scores.append((
            txn["transaction_id"],
            result["risk_score"],
            result["action"],
            txn["risk_label"]
        ))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores

def run_experiment_3_all_three(test_txns):
    """
    实验三：三路 RRF排名
    """
    clear_redis()
    scores = []
    for txn in test_txns:
        state = {
            "rule_result": run_rule_engine(txn["uid"], txn["device_id"], float(txn["amount"])),
            "vector_result": run_vector_detect(
                txn["uid"], txn["device_id"], float(txn["amount"]),
                txn["ip"], txn["payment_method"]
            ),
            "graph_result": run_graph_detect(txn["uid"], txn["device_id"]),
        }
        result = rrf_fusion_node(state)
        scores.append((txn["transaction_id"], result["risk_score"], result["action"], txn["risk_label"]))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def calc_review_recall(scores):
    """
    计算推送给人工关注（review + block）的召回率
    = 被识别为需要关注的异常交易数 / 总异常交易数
    """
    total_fraud = sum(1 for _, _, action, label in scores if label == "fraud")
    if total_fraud == 0:
        return 0.0

    reviewed = sum(
        1 for _, _, action, label in scores
        if label == "fraud" and action in ("review", "block")
    )
    return round(reviewed / total_fraud, 2)


def main():
    test_txns = load_all_transactions()
    fraud_count = sum(1 for txn in test_txns if txn["risk_label"] == "fraud")
    print(f"测试集: {len(test_txns)} 条交易（{len(test_txns) - fraud_count} 正常 + {fraud_count} 异常）\n")

    exp1 = run_experiment_1_rule_only(test_txns)
    print(f"实验一 仅规则引擎         审核召回率: {calc_review_recall(exp1)}")

    exp2 = run_experiment_2_rule_and_vector(test_txns)
    print(f"实验二 规则引擎+向量检测   审核召回率: {calc_review_recall(exp2)}")

    exp3 = run_experiment_3_all_three(test_txns)
    print(f"实验三 三路RRF融合        审核召回率: {calc_review_recall(exp3)}")

if __name__ == "__main__":
    main()