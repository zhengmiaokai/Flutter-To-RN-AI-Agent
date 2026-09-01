"""framework/config — Global configuration for the Flutter-to-RN converter."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class ModelRoute:
    """A model connection for one task, with an optional fallback.

    base_url/api_key default to the task's own primary connection, then to
    the global config when left unset (see Config.route_for).
    """

    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    fallback_model: Optional[str] = None
    fallback_base_url: Optional[str] = None
    fallback_api_key: Optional[str] = None


def _env_int(name: str, default):
    """Read an int env var, tolerating None/empty/garbage values."""
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class Config:
    """Global configuration for the Flutter-to-RN converter."""

    source_dir: str = "sample"
    target_dir: str = "output"
    template_dir: Optional[str] = None

    model: str = "deepseek-v4-pro"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    # task_type -> {model, base_url, api_key, fallback_model, ...}
    model_routes: dict = field(default_factory=dict)

    max_retries: int = 3
    timeout: float = 120.0
    llm_max_retries: int = 2
    scan_mode: str = "fast"
    skip_setup: bool = False
    skip_conversion: bool = False
    skip_verification: bool = False

    # Token budget guard (0 = unlimited) and harness features
    token_budget: int = 0
    cache_enabled: bool = True
    cache_ttl_hours: int = 24
    memory_enabled: bool = True

    state_file: str = ".flutter_to_rn_state.json"

    _loaded: bool = field(default=False, repr=False)

    def __post_init__(self):
        if not self._loaded:
            load_dotenv()
            self.api_key = self.api_key or os.getenv("OPENAI_API_KEY")
            self.base_url = self.base_url or os.getenv("OPENAI_BASE_URL")

            self.token_budget = _env_int("TOKEN_BUDGET", self.token_budget)
            self.cache_enabled = os.getenv("CACHE_ENABLED", str(self.cache_enabled)).lower() in ("1", "true", "yes")
            self.cache_ttl_hours = _env_int("CACHE_TTL_HOURS", self.cache_ttl_hours)
            self.memory_enabled = os.getenv("MEMORY_ENABLED", str(self.memory_enabled)).lower() in ("1", "true", "yes")
            # MODEL_ROUTES: JSON {task: {model, base_url, api_key, fallback_model, ...}}
            # Merged per-field with routes passed via kwargs/CLI so a CLI override
            # swaps only the named field and keeps the env entry's other fields.
            env_routes: dict = {}
            raw_routes = os.getenv("MODEL_ROUTES")
            if raw_routes:
                try:
                    parsed = json.loads(raw_routes)
                    if isinstance(parsed, dict):
                        env_routes = parsed
                except json.JSONDecodeError:
                    pass
            merged = dict(env_routes)
            for task, entry in self.model_routes.items():
                if isinstance(entry, dict):
                    merged[task] = {**merged.get(task, {}), **entry}
            self.model_routes = merged
            self._loaded = True

    @property
    def state_path(self) -> Path:
        return Path(self.target_dir) / self.state_file

    def validate(self) -> list[str]:
        errors = []
        if not self.api_key:
            errors.append("OPENAI_API_KEY is not set (env var, .env, or --api-key)")
        src = Path(self.source_dir) if self.source_dir else None
        if src and not src.exists():
            errors.append(f"Source directory not found: {self.source_dir}")
        return errors

    def route_for(self, task_type: str) -> ModelRoute:
        """Resolve the model connection for a task, falling back to the global model.

        Unset base_url/api_key fall back to the global config; a fallback's
        connection inherits the task's primary connection, then the global one.
        """
        entry = self.model_routes.get(task_type)
        if not entry:
            return ModelRoute(self.model, self.base_url, self.api_key)
        fbase = entry.get("fallback_base_url") or entry.get("base_url") or self.base_url
        fkey = entry.get("fallback_api_key") or entry.get("api_key") or self.api_key
        return ModelRoute(
            model=entry.get("model") or self.model,
            base_url=entry.get("base_url") or self.base_url,
            api_key=entry.get("api_key") or self.api_key,
            fallback_model=entry.get("fallback_model"),
            fallback_base_url=fbase,
            fallback_api_key=fkey,
        )


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


def init_config(**kwargs) -> Config:
    global _config
    _config = Config(**kwargs)
    _config._loaded = True
    return _config
