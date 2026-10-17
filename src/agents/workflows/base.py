from abc import ABC, abstractmethod
from typing import Any, ClassVar

from langchain_core.runnables import Runnable


class WorkflowExecution(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    version: ClassVar[str]

    def __init__(self) -> None:
        self._graph: Runnable[Any, Any] | None = None

    @property
    def graph(self) -> Runnable[Any, Any]:
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    @abstractmethod
    async def run(self, thread_id: str, input: dict[str, Any]) -> Any: ...

    @abstractmethod
    async def resume(self, thread_id: str, input: dict[str, Any]) -> Any: ...

    @abstractmethod
    def _build_graph(self) -> Runnable[Any, Any]: ...
