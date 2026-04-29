from app.databases.milvus_client import MilvusClientWrapper
from app.services.embedding_client import get_embedding

get_behavior_text(player_id: str, device_id: str, amount: float, ip: str, payment_method: str) -> str
    # 拼接格式同 init_data.py 第 9 步：
    # "uid:{player_id} amount:{amount} device:{device_id} ip:{ip} payment:{payment_method}"

search_similar_anomalies(text: str, top_k: int = 5) -> list[dict]
    # 1. vec = get_embedding(text)
    # 2. _get_milvus().search_similar("transaction_behaviors", vec, top_k)
    # 3. 如果结果为空，返回空列表
    # 4. 返回 distance 取前 top_k 的条目

run_vector_detect(player_id: str, device_id: str, amount: float, ip: str, payment_method: str) -> dict:
    # 返回结构：
    # {
    #     "similarity_score": float,      # Top-1 相似度，无匹配时 0.0
    #     "top_matches": [
    #         {"transaction_id": str, "similarity": float},
    #     ],
    #     "has_match": bool,
    # }