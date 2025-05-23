from __future__ import annotations
from pathlib import Path
from threading import Lock
from typing import Any, Optional, Dict
import tomli
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class BaseConfig(BaseModel):
    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

class CatalogConfig(BaseConfig):
    auto_register: bool = Field(default=False, description="Automatically register workflows on startup")
    options: dict[str, Any] = Field(default={}, description="Additional options for the catalog")

class ExecutorConfig(BaseConfig):
    """Configuration for workflow executor."""
    max_workers: int = Field(default=None, description="Maximum number of worker threads")
    default_timeout: int = Field(default=0, description="Default task timeout in seconds")
    retry_attempts: int = Field(default=3, description="Default number of retry attempts")
    retry_delay: int = Field(default=1, description="Default delay between retries in seconds")
    retry_backoff: int = Field(default=2, description="Default backoff multiplier for retries")
    execution_mode: str = Field(default="local", description="Execution mode: 'local' or 'distributed'")
    distributed_config: dict[str, Any] = Field(default_factory=dict, description="Configuration for distributed execution")
    available_cpu: int = Field(default=4, description="Available CPU cores")
    available_memory: float = Field(default=8, description="Available memory in GB")
    available_gpu: int = Field(default=0, description="Available GPU units")
    default_priority: int = Field(default=10, description="Default task priority (lower is higher)")
    external_scheduler: Optional[Dict[str, Any]] = Field(default=None, description="Configuration for external schedulers like Kubernetes or Airflow")

class EncryptionConfig(BaseConfig):
    encryption_key: str | None = Field(default=None, description="Encryption key for sensitive data")

class CacheConfig(BaseConfig):
    backend: str = Field(default="file", description="Cache backend: 'file', 'redis', or 'memcached'")
    default_ttl: Optional[int] = Field(default=None, description="Default cache TTL in seconds")
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database")
    memcached_host: str = Field(default="localhost", description="Memcached host")
    memcached_port: int = Field(default=11211, description="Memcached port")

class FluxConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLUX_", env_nested_delimiter="__", case_sensitive=False)
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    server_port: int = Field(default=8000, description="Port for the API server")
    server_host: str = Field(default="localhost", description="Host for the API server")
    api_url: str = Field(default="http://localhost:8000", description="API URL for remote execution")
    home: str = Field(default=".flux", description="Home directory for Flux")
    cache_path: str = Field(default=".cache", description="Path for cache directory")
    local_storage_path: str = Field(default=".data", description="Path for local storage directory")
    serializer: str = Field(default="pkl", description="Default serializer (json or pkl)")
    database_url: str = Field(default="sqlite:///.flux/flux.db", description="Database URL")
    database_type: str = Field(default="sqlite", description="Database type: 'sqlite' or 'postgresql'")
    executor: ExecutorConfig = Field(default_factory=ExecutorConfig)
    security: EncryptionConfig = Field(default_factory=EncryptionConfig)
    catalog: CatalogConfig = Field(default_factory=CatalogConfig)
    storage: dict[str, Any] = Field(default_factory=dict, description="Storage backend configuration")
    plugins: dict[str, Any] = Field(default_factory=dict, description="Plugin configuration")
    monitoring: dict[str, Any] = Field(default_factory=dict, description="Monitoring configuration")
    cloud: dict[str, Any] = Field(default_factory=dict, description="Cloud service configuration")

    @field_validator("serializer")
    def validate_serializer(cls, v: str) -> str:
        if v not in ["json", "pkl"]:
            raise ValueError("Serializer must be either 'json' or 'pkl'")
        return v

    @field_validator("executor")
    def validate_executor(cls, v: ExecutorConfig) -> ExecutorConfig:
        if v.execution_mode not in ["local", "distributed"]:
            raise ValueError("Execution mode must be 'local' or 'distributed'")
        return v

    @classmethod
    def load(cls) -> FluxConfig:
        config = cls._load_from_config()
        config = {**config, **cls._load_from_pyproject()}
        return cls(**config)

    @staticmethod
    def _load_from_pyproject() -> dict[str, Any]:
        return FluxConfig._load_from_toml("pyproject.toml", ["tool", "flux"])

    @staticmethod
    def _load_from_config() -> dict[str, Any]:
        return FluxConfig._load_from_toml("flux.toml", ["flux"])

    @staticmethod
    def _load_from_toml(file_name: str, keys: list[str]) -> dict[str, Any]:
        file_path = Path(file_name)
        if not file_path.exists():
            return {}
        try:
            with open(file_path, "rb") as f:
                config = tomli.load(f)
                for key in keys:
                    config = config.get(key, {})
                return config
        except Exception:
            return {}

class Configuration:
    _instance: Configuration | None = None
    _lock: Lock = Lock()
    _config: FluxConfig | None = None

    def __new__(cls) -> Configuration:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            with self._lock:
                if self._config is None:
                    self._config = FluxConfig.load()

    @property
    def settings(self) -> FluxConfig:
        if self._config is None:
            with self._lock:
                if self._config is None:
                    self._config = FluxConfig.load()
        return self._config

    def reload(self) -> None:
        with self._lock:
            self._config = FluxConfig.load()

    def override(self, **kwargs) -> None:
        with self._lock:
            if self._config is None:
                self._config = FluxConfig.load()
            config_dict = self._config.model_dump()
            self._update_nested_dict(config_dict, kwargs)
            self._config = FluxConfig(**config_dict)

    def reset(self) -> None:
        with self._lock:
            self._config = None

    def _update_nested_dict(self, d: dict, u: dict) -> None:
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._update_nested_dict(d[k], v)
            else:
                d[k] = v

    @staticmethod
    def get() -> Configuration:
        return Configuration()