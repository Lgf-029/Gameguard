import redis
import time
from app.config import REDIS_HOST, REDIS_PORT


class RedisClient:
    def __init__(self):
        self.client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
        )

    def set_cache(self, key: str, value: str, ttl: int = 3600) -> None:
        """设置缓存，默认1小时过期"""
        self.client.set(key, value, ex=ttl)

    def get_cache(self, key: str) -> str | None:
        """获取缓存，不存在返回 None"""
        return self.client.get(key)

    def delete_cache(self, key: str) -> None:
        """删除缓存"""
        self.client.delete(key)

    def sliding_window_count(self, key: str, window_seconds: int = 3600) -> int:
        """滑动窗口计数，返回时间窗口内的操作次数"""
        now = time.time()
        start = now - window_seconds
        self.client.zremrangebyscore(key, 0, start)
        return self.client.zcard(key)

    def add_event(self, key: str, value: str) -> None:
        """向滑动窗口添加事件记录"""
        self.client.zadd(key, {value: time.time()})

    def close(self):
        self.client.close()