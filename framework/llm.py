"""framework/llm — LangChain ChatOpenAI-powered LLM client.

Replaces the raw openai.OpenAI client with LangChain's ChatOpenAI,
bringing streaming, structured output, and token tracking support.
Compatible with any OpenAI-compatible API (DeepSeek, Ollama, etc.).
"""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from framework.config import Config


class LLMClient:
    """LangChain-based LLM client.

    Wraps ChatOpenAI to work with any OpenAI-compatible provider.
    Supports the original chat()/chat_with_messages() API for backward
    compatibility, plus direct access to the ChatOpenAI instance for
    use with create_agent() (from langchain.agents) and LangGraph workflows.

    Key LangChain features used:
    - ChatOpenAI (provider-agnostic, supports function/tool calling)
    - Structured output via .with_structured_output()
    - Streaming via .stream()
    - Tool binding for ReAct agents
    """

    def __init__(self, config: Config):
        self._config = config
        self._llm: Optional[ChatOpenAI] = None

    # ---- LangChain ChatOpenAI instance --------------------------------------

    @property
    def llm(self) -> ChatOpenAI:
        """Get the underlying ChatOpenAI instance.

        Use this directly for LangChain agent creation and advanced features.
        """
        if self._llm is None:
            kwargs: dict[str, Any] = {
                "model": self._config.model,
                "api_key": self._config.api_key,
                "temperature": 0.2,
                "timeout": self._config.timeout,
                "max_retries": self._config.llm_max_retries,
                "max_tokens": 4096,
            }
            if self._config.base_url:
                kwargs["base_url"] = self._config.base_url
            self._llm = ChatOpenAI(**kwargs)
        return self._llm

    # ---- Backward-compatible chat API (powered by LangChain) -----------------

    def chat(self, system_prompt: str, user_message: str, **kwargs) -> str:
        """Send a chat completion and return the response text.

        Internally uses ChatOpenAI.invoke() for LangChain-powered completions.
        """
        temperature = kwargs.pop("temperature", 0.2)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]
        response = self.llm.invoke(messages, **{"temperature": temperature, **kwargs})
        return response.content

    def chat_with_messages(self, messages: list[dict], **kwargs) -> str:
        """Send a multi-turn chat completion.

        Accepts OpenAI-format message dicts and converts them to
        LangChain message objects internally.
        """
        from langchain_core.messages import BaseMessage

        temperature = kwargs.pop("temperature", 0.2)
        lc_messages: list[BaseMessage] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "user":
                lc_messages.append(HumanMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))

        response = self.llm.invoke(lc_messages, **{"temperature": temperature, **kwargs})
        return response.content

    # ---- LangGraph agent factory --------------------------------------------

    def create_agent(
        self,
        tools: list,
        system_prompt: str,
        name: str = "agent",
    ):
        """Create a LangGraph ReAct agent bound to this LLM.

        Args:
            tools: List of LangChain @tool-decorated functions or BaseTool objects.
            system_prompt: System prompt for the agent.
            name: Agent name for graph node identification.

        Returns:
            A compiled LangGraph agent (callable via .invoke()).
        """
        return create_agent(
            model=self.llm,
            tools=tools,
            system_prompt=system_prompt,
            name=name,
        )

    def chat_prompt(self, system_prompt: str, user_message: str, **kwargs) -> str:
        """Alias for chat() — for readability."""
        return self.chat(system_prompt, user_message, **kwargs)
