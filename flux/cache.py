# File: C:\Users\KMeuse\Desktop\Projects\flux\flux\cache.py
from __future__ import annotations
from typing import Any, Optional
from flux.cache_backends import CacheBackend, FileCacheBackend, RedisCacheBackend, MemcachedCacheBackend
from flux.config import Configuration

class CacheManager:
    def __init__(self):
        self.backend = self._get_backend()

    def _get_backend(self) -> CacheBackend:
        cache_config = Configuration.get().settings.cache
        backend_type = cache_config.get("backend", "file")
        if backend_type == "redis":
            return RedisCacheBackend()
        elif backend_type == "memcached":
            return MemcachedCacheBackend()
        return FileCacheBackend()

    @staticmethod
    def default() -> CacheManager:
        return CacheManager()

    def get(self, key: str, version: Optional[str] = None) -> Optional[Any]:
        return self.backend.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None, version: Optional[str] = None) -> None:
        self.backend.set(key, value, ttl, version)

    def delete(self, key: str) -> None:
        self.backend.delete(key)

    def validate(self, key: str, version: Optional[str] = None) -> bool:
        return self.backend.validate(key, version)
