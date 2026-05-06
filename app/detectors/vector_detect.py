from app.databases.milvus_client import MilvusClient
from app.services.embedding_client import get_embedding

_milvus = None

def _get_milvus():
    global _milvus
    if _milvus is None:
        _milvus = MilvusClient()
    return _milvus

# 拼接交易文本
def get_behavior_text(player_id: str, device_id: str, amount: float, ip: str, payment_method: str) -> str:
    return f"uid:{player_id} amount:{amount} device:{device_id} ip:{ip} payment:{payment_method}"

# 查Milvus返回Top_k匹配
def search_similar_anomalies(text: str, top_k: int = 5) -> list[dict]:
    vec = get_embedding(text)
    milvus = _get_milvus()
    collection = "transaction_behaviors"
    if milvus.client.has_collection(collection):
        milvus.client.load_collection(collection)
    results = milvus.search_similar(collection, vec, top_k)
    matches = []
    for item in results:
        distance = item.get("distance", 0.0)
        similarity = 1.0 - distance
        matches.append({
            "transaction_id": item.get("id", ""),
            "similarity": round(similarity, 4),
        })
    return matches

# 向量检测入口
def run_vector_detect(player_id: str, device_id: str, amount: float, ip: str, payment_method: str) -> dict:
    text = get_behavior_text(player_id,device_id,amount,ip,payment_method)
    matches = search_similar_anomalies(text,top_k=5)
    has_match = len(matches) > 0
    top_similarity = matches[0]["similarity"] if has_match else 0.0
    return {
        "similarity_score":top_similarity,
        "top_matches":matches,
        "has_match":has_match,
    }
