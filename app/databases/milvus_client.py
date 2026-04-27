from pymilvus import MilvusClient
from app.config import MILVUS_HOST, MILVUS_PORT, MILVUS_USER, MILVUS_PASSWORD


class MilvusClientWrapper:
    def __init__(self):
        self.client = MilvusClient(
            uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}",
            user=MILVUS_USER,
            password=MILVUS_PASSWORD,
        )

    def create_collection(self, collection_name: str, dimension: int) -> None:
        """创建集合"""
        if self.client.has_collection(collection_name):
            return
        self.client.create_collection(
            collection_name=collection_name,
            dimension=dimension,
            metric_type="COSINE",
        )

    def insert_vectors(self, collection_name: str, vectors: list[list[float]], ids: list[str]) -> dict:
        """插入向量，返回插入结果"""
        return self.client.insert(
            collection_name=collection_name,
            data=[{"id": id_, "vector": vec} for id_, vec in zip(ids, vectors)],
        )

    def search_similar(self, collection_name: str, vector: list[float], top_k: int = 10) -> list[dict]:
        """相似度检索，返回top_k结果"""
        results = self.client.search(
            collection_name=collection_name,
            data=[vector],
            limit=top_k,
            output_fields=["id"],
        )
        return results[0] if results else []

    def close(self):
        self.client.close()