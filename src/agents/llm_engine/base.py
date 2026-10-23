from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, overload

from agents.dtos.message import MessageDTO

type ToolType = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class GenerationMetadata:
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    elapsed_seconds: float | None = None
    tokens_per_second: float | None = None
    finish_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True, slots=True)
class GenerationResult[T]:
    raw_text: str
    structured_output: T | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: GenerationMetadata = field(default_factory=GenerationMetadata)


@dataclass(frozen=True, slots=True)
class ToolCallDelta:
    index: int
    id: str | None = None
    name: str | None = None
    args_json_delta: str | None = None


@dataclass(frozen=True, slots=True)
class GenerationChunk:
    text_delta: str = ''
    tool_call_delta: ToolCallDelta | None = None


@dataclass(frozen=True, slots=True)
class GenerationFinal:
    raw_text: str
    tool_calls: list[ToolCall]
    usage: GenerationMetadata


class ILLMEngine(Protocol):
    @overload
    async def generate(
        self,
        messages: list[MessageDTO],
        system_prompt: str,
        *,
        output_schema: None = None,
        tools: list[ToolType] | None = None,
        **kwargs: Any,
    ) -> GenerationResult[str]: ...

    @overload
    async def generate[T](
        self,
        messages: list[MessageDTO],
        system_prompt: str,
        *,
        output_schema: type[T],
        tools: list[ToolType] | None = None,
        **kwargs: Any,
    ) -> GenerationResult[T]: ...

    async def generate[T](
        self,
        messages: list[MessageDTO],
        system_prompt: str,
        *,
        output_schema: type[T] | None = None,
        tools: list[ToolType] | None = None,
        **kwargs: Any,
    ) -> GenerationResult[T] | GenerationResult[str]: ...

    def stream(
        self,
        messages: list[MessageDTO],
        system_prompt: str,
        *,
        tools: list[ToolType] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[GenerationChunk | GenerationFinal]: ...
