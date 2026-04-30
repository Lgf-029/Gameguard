from pymilvus import MilvusClient as PyMilvusClient
from pymilvus import DataType
from app.config import MILVUS_HOST, MILVUS_PORT, MILVUS_USER, MILVUS_PASSWORD

class MilvusClient:
    def __init__(self):
        self.client = PyMilvusClient(
            uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}",
            user=MILVUS_USER,
            password=MILVUS_PASSWORD,
        )

    def create_collection(self, collection_name: str, dimension: int) -> None:
        """创建集合，存在则跳过"""
        if self.client.has_collection(collection_name):
            return
        schema = self.client.create_schema()
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dimension)
        self.client.create_collection(
            collection_name=collection_name,
            schema=schema,
            metric_type="COSINE",
        )

    def insert_vectors(self, collection_name: str, vectors: list[list[float]], ids: list[str]) -> dict:
        """插入向量并创建IVF_FLAT索引"""
        result = self.client.insert(
            collection_name=collection_name,
            data=[{"id": id_, "vector": vec} for id_, vec in zip(ids, vectors)],
        )
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128},
        )
        self.client.create_index(
            collection_name=collection_name,
            index_params=index_params,
        )
        return result

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