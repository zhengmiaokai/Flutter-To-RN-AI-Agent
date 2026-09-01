"""framework/llm — ChatOpenAI instance pool for any number of routed models.

The harness is the only LLM entry point. Model routing lets each task talk to
its own model (config.model_routes / MODEL_ROUTES), so the pool holds one
ChatOpenAI instance per (base_url, model, api_key) connection. Calls without
a route fall back to the global model (config.model / --model). Per-task
adaptation happens at the call level: the harness sizes each request
(max_tokens etc.) via invoke kwargs.
"""

from __future__ import annotations

from typing import Any, Optional

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from framework.config import Config


class LLMClient:
    """Pool of ChatOpenAI instances for any OpenAI-compatible provider."""

    def __init__(self, config: Config):
        self._config = config
        self._pool: dict[str, ChatOpenAI] = {}

    # ---- instance pool ---------------------------------------------------

    def _pool_key(self, model: str, base_url: Optional[str], api_key: Optional[str]) -> str:
        return f"{base_url or ''}|{model}|{api_key or ''}"

    def get_llm(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> ChatOpenAI:
        """Get (and lazily create) the ChatOpenAI instance for a connection.

        Any arg left unset falls back to the global config, so get_llm() with
        no args returns the global model's instance (unchanged behavior).
        """
        model = model or self._config.model
        base_url = base_url or self._config.base_url
        api_key = api_key or self._config.api_key
        key = self._pool_key(model, base_url, api_key)
        llm = self._pool.get(key)
        if llm is None:
            kwargs: dict[str, Any] = {
                "model": model,
                "api_key": api_key,
                "temperature": 0.2,
                "timeout": self._config.timeout,
                "max_retries": self._config.llm_max_retries,
            }
            if base_url:
                kwargs["base_url"] = base_url
            llm = ChatOpenAI(**kwargs)
            self._pool[key] = llm
        return llm

    # ---- ReAct agent factory ----------------------------------------------

    def create_agent(
        self,
        tools: list,
        system_prompt: str,
        name: str = "agent",
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """Build a compiled LangGraph ReAct agent bound to this client's model.

        Returns a CompiledStateGraph callable via .invoke({"messages": [...]}).
        """
        llm = self.get_llm(model=model, base_url=base_url, api_key=api_key)
        return create_agent(
            model=llm,
            tools=list(tools),
            system_prompt=system_prompt,
            name=name,
        )
