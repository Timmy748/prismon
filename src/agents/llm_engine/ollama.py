from collections.abc import AsyncIterator, Mapping
from time import monotonic
from typing import Any, overload

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
)
from langchain_ollama import ChatOllama

from agents.dtos.message import MessageDTO
from agents.entities.message import SenderType
from agents.llm_engine.base import (
    GenerationChunk,
    GenerationFinal,
    GenerationMetadata,
    GenerationResult,
    ToolCall,
    ToolCallDelta,
    ToolType,
)
from agents.settings import get_settings


class OllamaEngine:
    """One Ollama engine with per-call tool and structured-output options."""

    def __init__(self, llm: BaseChatModel | None = None) -> None:
        self._llm: BaseChatModel = (
            llm if llm is not None else self._create_llm()
        )

    @staticmethod
    def _create_llm() -> BaseChatModel:
        settings = get_settings()
        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            temperature=settings.OLLAMA_TEMPERATURE,
        )

    @staticmethod
    def _to_langchain_messages(
        messages: list[MessageDTO], system_prompt: str
    ) -> list[SystemMessage | HumanMessage | AIMessage]:
        result: list[SystemMessage | HumanMessage | AIMessage] = [
            SystemMessage(content=system_prompt)
        ]
        for message in messages:
            if message.sender_type == SenderType.USER:
                result.append(HumanMessage(content=message.text))
            else:
                result.append(AIMessage(content=message.text))
        return result

    @staticmethod
    def _metadata(
        llm: BaseChatModel,
        response: AIMessage | AIMessageChunk,
        elapsed_seconds: float,
    ) -> GenerationMetadata:
        response_metadata = response.response_metadata
        token_usage = response.usage_metadata or {}
        input_tokens = token_usage.get('input_tokens')
        if input_tokens is None:
            input_tokens = response_metadata.get('prompt_eval_count')
        output_tokens = token_usage.get('output_tokens')
        if output_tokens is None:
            output_tokens = response_metadata.get('eval_count')
        total_tokens = token_usage.get('total_tokens')
        if (
            total_tokens is None
            and isinstance(input_tokens, (int, float))
            and isinstance(output_tokens, (int, float))
        ):
            total_tokens = input_tokens + output_tokens

        eval_duration = response_metadata.get('eval_duration')
        generation_seconds = elapsed_seconds
        if isinstance(eval_duration, (int, float)) and eval_duration > 0:
            generation_seconds = eval_duration / 1_000_000_000
        tokens_per_second = None
        if isinstance(output_tokens, (int, float)) and output_tokens > 0:
            if generation_seconds > 0:
                tokens_per_second = output_tokens / generation_seconds

        model = response_metadata.get('model') or getattr(llm, 'model', None)
        finish_reason = response_metadata.get(
            'done_reason'
        ) or response_metadata.get('finish_reason')
        return GenerationMetadata(
            model=str(model) if model is not None else None,
            input_tokens=(
                int(input_tokens) if input_tokens is not None else None
            ),
            output_tokens=(
                int(output_tokens) if output_tokens is not None else None
            ),
            total_tokens=(
                int(total_tokens) if total_tokens is not None else None
            ),
            elapsed_seconds=elapsed_seconds,
            tokens_per_second=(
                float(tokens_per_second)
                if tokens_per_second is not None
                else None
            ),
            finish_reason=(
                str(finish_reason) if finish_reason is not None else None
            ),
        )

    @staticmethod
    def _tool_calls(
        response: AIMessage | AIMessageChunk | None,
    ) -> list[ToolCall]:
        calls = getattr(response, 'tool_calls', ()) or ()
        normalized: list[ToolCall] = []
        for call in calls:
            if not isinstance(call, Mapping):
                continue
            name = call.get('name')
            args = call.get('args')
            if not isinstance(name, str) or not isinstance(args, Mapping):
                continue
            call_id = call.get('id')
            normalized.append(ToolCall(str(call_id or ''), name, dict(args)))
        return normalized

    @staticmethod
    def _tool_call_deltas(chunk: AIMessageChunk) -> list[ToolCallDelta]:
        deltas: list[ToolCallDelta] = []
        for call in chunk.tool_call_chunks:
            index = call.get('index')
            if not isinstance(index, int):
                continue
            deltas.append(
                ToolCallDelta(
                    index=index,
                    id=call.get('id'),
                    name=call.get('name'),
                    args_json_delta=call.get('args'),
                )
            )
        return deltas

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

    async def generate(
        self,
        messages: list[MessageDTO],
        system_prompt: str,
        *,
        output_schema: type[Any] | None = None,
        tools: list[ToolType] | None = None,
        **kwargs: Any,
    ) -> GenerationResult[Any]:
        started = monotonic()
        if output_schema is not None:
            runnable = self._llm.with_structured_output(
                output_schema, include_raw=True
            )
        elif tools:
            runnable = self._llm.bind_tools(tools)
        else:
            runnable = self._llm

        response = await runnable.ainvoke(
            self._to_langchain_messages(messages, system_prompt), **kwargs
        )
        elapsed = monotonic() - started
        structured_output = None
        raw_response = response
        if output_schema is not None:
            if not isinstance(response, Mapping):
                raise TypeError(
                    'Structured runnable returned an invalid envelope'
                )
            structured_output = response.get('parsed')
            raw_response = response.get('raw')
            error = response.get('parsing_error')
            if structured_output is None:
                raise ValueError('Structured output parsing failed') from error
        if not isinstance(raw_response, (AIMessage, AIMessageChunk)):
            raise TypeError('Chat model runnable returned an invalid message')

        return GenerationResult(
            raw_text=str(raw_response.content),
            structured_output=structured_output,
            tool_calls=self._tool_calls(raw_response),
            usage=self._metadata(self._llm, raw_response, elapsed),
        )

    async def stream(
        self,
        messages: list[MessageDTO],
        system_prompt: str,
        *,
        tools: list[ToolType] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[GenerationChunk | GenerationFinal]:
        runnable = self._llm.bind_tools(tools) if tools else self._llm
        started = monotonic()
        text_parts: list[str] = []
        final_chunk: AIMessageChunk | None = None
        async for chunk in runnable.astream(
            self._to_langchain_messages(messages, system_prompt), **kwargs
        ):
            if not isinstance(chunk, AIMessageChunk):
                continue
            final_chunk = chunk if final_chunk is None else final_chunk + chunk
            text_delta = str(chunk.content) if chunk.content else ''
            if text_delta:
                text_parts.append(text_delta)
            deltas = self._tool_call_deltas(chunk)
            if deltas:
                for delta in deltas:
                    yield GenerationChunk(
                        text_delta=text_delta, tool_call_delta=delta
                    )
                    text_delta = ''
            elif text_delta:
                yield GenerationChunk(text_delta=text_delta)
        final_chunk = final_chunk or AIMessageChunk(content='')
        yield GenerationFinal(
            raw_text=''.join(text_parts),
            tool_calls=self._tool_calls(final_chunk),
            usage=self._metadata(self._llm, final_chunk, monotonic() - started),
        )
