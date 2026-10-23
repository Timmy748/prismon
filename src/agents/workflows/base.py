from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, ClassVar

from langchain_core.runnables import Runnable

from agents.dtos.message import CreateMessageDTO
from agents.llm_engine.base import ILLMEngine


class WorkflowExecution(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    version: ClassVar[str]

    def __init__(self, engine: ILLMEngine) -> None:
        self._graph: Runnable[Any, Any] | None = None
        self._engine: ILLMEngine = engine

    @property
    def graph(self) -> Runnable[Any, Any]:
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    @abstractmethod
    async def run(
        self, thread_id: str, input: dict[str, Any]
    ) -> CreateMessageDTO: ...

    async def stream(
        self, thread_id: str, input: dict[str, Any]
    ) -> AsyncIterator[Any]:
        """Stream workflow output, yielding the completed result by default.

        Streaming workflows can override this to yield incremental events.
        The default keeps existing workflows compatible with callers that
        consume the stream interface.
        """
        yield await self.run(thread_id, input)

    @abstractmethod
    async def resume(
        self, thread_id: str, input: dict[str, Any]
    ) -> CreateMessageDTO: ...

    @abstractmethod
    def _build_graph(self) -> Runnable[Any, Any]: ...
