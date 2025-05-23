from typing import Any, Optional, Set
from cachetools import LRUCache
from flux.cache_backends import CacheBackend, RedisCacheBackend, FileCacheBackend
from flux.config import Configuration

class CacheInvalidator:
    def __init__(self, cache_manager: 'CacheManager'):
        self.cache_manager = cache_manager
        self.tags: dict[str, Set[str]] = {}  # Map tags to cache keys

    def tag_key(self, key: str, tags: Set[str]):
        for tag in tags:
            self.tags.setdefault(tag, set()).add(key)

    def invalidate_by_tag(self, tag: str):
        keys = self.tags.get(tag, set())
        for key in keys:
            self.cache_manager.delete(key)
        self.tags.pop(tag, None)

    def invalidate_by_event(self, event_type: str, workflow_name: str):
        if event_type in ['WORKFLOW_UPDATED', 'WORKFLOW_DELETED']:
            self.invalidate_by_tag(f"workflow:{workflow_name}")

class CacheManager:
    def __init__(self):
        self.memory_cache = LRUCache(maxsize=Configuration.get().settings.cache.get('memory_maxsize', 1000))
        self.persistent_backend = self._get_persistent_backend()
        self.invalidator = CacheInvalidator(self)

    def _get_persistent_backend(self) -> CacheBackend:
        cache_config = Configuration.get().settings.cache
        backend_type = cache_config.get("backend", "file")
        if backend_type == "redis":
            return RedisCacheBackend()
        elif backend_type == "memcached":
            return MemcachedCacheBackend()
        return FileCacheBackend()

    @staticmethod
    def default() -> 'CacheManager':
        return CacheManager()

    def get(self, key: str, version: Optional[str] = None) -> Optional[Any]:
        # Check memory cache first
        if key in self.memory_cache and self.validate(key, version):
            return self.memory_cache[key]
        # Fall back to persistent cache
        value = self.persistent_backend.get(key)
        if value is not None and self.validate(key, version):
            self.memory_cache[key] = value  # Populate memory cache
            return value
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None, version: Optional[str] = None, tags: Optional[Set[str]] = None) -> None:
        self.memory_cache[key] = value
        self.persistent_backend.set(key, value, ttl, version)
        if tags:
            self.invalidator.tag_key(key, tags)

    def delete(self, key: str) -> None:
        self.memory_cache.pop(key, None)
        self.persistent_backend.delete(key)

    def validate(self, key: str, version: Optional[str] = None) -> bool:
        return self.persistent_backend.validate(key, version)

    def warm_up(self, keys: list[str]):
        for key in keys:
            value = self.persistent_backend.get(key)
            if value is not None:
                self.memory_cache[key] = value
