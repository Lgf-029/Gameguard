from elasticsearch import Elasticsearch
from app.config import ES_HOST, ES_PORT


class ESClient:
    def __init__(self):
        self.client = Elasticsearch(
            hosts=[{"host": ES_HOST, "port": ES_PORT}]
        )

    def index_log(self, index: str, doc: dict) -> str:
        """写入日志，返回文档_id"""
        result = self.client.index(index=index, body=doc)
        return result["_id"]

    def search_logs(self, index: str, query: dict, size: int = 20) -> list[dict]:
        """检索日志"""
        result = self.client.search(index=index, body={
            "query": query,
            "size": size,
            "sort": [{"timestamp": {"order": "desc"}}]
        })
        return [hit["_source"] for hit in result["hits"]["hits"]]

    def close(self):
        self.client.close()