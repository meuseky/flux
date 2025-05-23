from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
import dill
import redis
import pymemcache.client
from flux.config import Configuration

class CacheBackend(ABC):
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError()

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None, version: Optional[str] = None) -> None:
        raise NotImplementedError()

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    def validate(self, key: str, version: Optional[str] = None) -> bool:
        raise NotImplementedError()

class FileCacheBackend(CacheBackend):
    def __init__(self):
        self.settings = Configuration.get().settings
        self.cache_path = Path(self.settings.home) / self.settings.cache_path
        self.cache_path.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> Optional[Any]:
        cache_file = self._get_file_name(key)
        if cache_file.exists():
            with open(cache_file, "rb") as f:
                data = dill.load(f)
                if self.validate(key, data.get("version")):
                    return data["value"]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None, version: Optional[str] = None) -> None:
        cache_file = self._get_file_name(key)
        data = {
            "value": value,
            "version": version,
            "created_at": datetime.now(),
            "ttl": ttl
        }
        with open(cache_file, "wb") as f:
            dill.dump(data, f)

    def delete(self, key: str) -> None:
        cache_file = self._get_file_name(key)
        if cache_file.exists():
            cache_file.unlink()

    def validate(self, key: str, version: Optional[str] = None) -> bool:
        cache_file = self._get_file_name(key)
        if not cache_file.exists():
            return False
        with open(cache_file, "rb") as f:
            data = dill.load(f)
            if version and data.get("version") != version:
                return False
            if data.get("ttl"):
                expiry = data["created_at"] + timedelta(seconds=data["ttl"])
                if datetime.now() > expiry:
                    self.delete(key)
                    return False
            return True

    def _get_file_name(self, key: str) -> Path:
        return self.cache_path / f"{key}.pkl"

class RedisCacheBackend(CacheBackend):
    def __init__(self):
        cache_config = Configuration.get().settings.cache
        self.client = redis.Redis(
            host=cache_config.get("redis_host", "localhost"),
            port=cache_config.get("redis_port", 6379),
            db=cache_config.get("redis_db", 0)
        )

    def get(self, key: str) -> Optional[Any]:
        if self.validate(key):
            data = self.client.get(key)
            if data:
                return dill.loads(data)["value"]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None, version: Optional[str] = None) -> None:
        data = {
            "value": value,
            "version": version,
            "created_at": datetime.now().isoformat(),
            "ttl": ttl
        }
        self.client.set(key, dill.dumps(data), ex=ttl)

    def delete(self, key: str) -> None:
        self.client.delete(key)

    def validate(self, key: str, version: Optional[str] = None) -> bool:
        data = self.client.get(key)
        if not data:
            return False
        data = dill.loads(data)
        if version and data.get("version") != version:
            return False
        if data.get("ttl"):
            created_at = datetime.fromisoformat(data["created_at"])
            expiry = created_at + timedelta(seconds=data["ttl"])
            if datetime.now() > expiry:
                self.delete(key)
                return False
        return True

class MemcachedCacheBackend(CacheBackend):
    def __init__(self):
        cache_config = Configuration.get().settings.cache
        self.client = pymemcache.client.Client(
            (cache_config.get("memcached_host", "localhost"), cache_config.get("memcached_port", 11211))
        )

    def get(self, key: str) -> Optional[Any]:
        if self.validate(key):
            data = self.client.get(key)
            if data:
                return dill.loads(data)["value"]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None, version: Optional[str] = None) -> None:
        data = {
            "value": value,
            "version": version,
            "created_at": datetime.now().isoformat(),
            "ttl": ttl
        }
        self.client.set(key, dill.dumps(data), expire=ttl or 0)

    def delete(self, key: str) -> None:
        self.client.delete(key)

    def validate(self, key: str, version: Optional[str] = None) -> bool:
        data = self.client.get(key)
        if not data:
            return False
        data = dill.loads(data)
        if version and data.get("version") != version:
            return False
        if data.get("ttl"):
            created_at = datetime.fromisoformat(data["created_at"])
            expiry = created_at + timedelta(seconds=data["ttl"])
            if datetime.now() > expiry:
                self.delete(key)
                return False
        return True
