from typing import Any, AsyncIterator, Callable, Protocol

from agents.dtos.message import MessageDTO

type ToolType = Callable[..., Any]


class ILLMEngine(Protocol):
    def bind_tools(self, tools: list[ToolType]) -> 'ILLMEngine': ...

    async def generate(
        self, messages: list[MessageDTO], system_prompt: str, **kwargs: Any
    ) -> str: ...

    def stream(
        self, messages: list[MessageDTO], system_prompt: str, **kwargs: Any
    ) -> AsyncIterator[str]: ...

    async def generate_strutured[T](
        self,
        schema: type[T],
        messages: list[MessageDTO],
        system_prompt: str,
        **kwargs: Any,
    ) -> T: ...
