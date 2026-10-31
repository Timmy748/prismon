from abc import ABC, abstractmethod
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

from agents.dtos.message import MessageDTO
from agents.entities.message import SenderType
from agents.llm_engine.base import (
    GenerationChunk,
    GenerationFinal,
    GenerationMetadata,
    GenerationResult,
    ILLMEngine,
    ToolCall,
    ToolCallDelta,
    ToolType,
)
from infra.logs import get_logger

logger = get_logger(__name__)


class LangChainEngine(ABC, ILLMEngine):
    def __init__(
        self,
        api_key: str,
        llm: BaseChatModel | None = None,
    ) -> None:
        self._llm = llm if llm is not None else self._create_llm(api_key)

    @staticmethod
    @abstractmethod
    def _create_llm(api_key: str) -> BaseChatModel: ...

    @staticmethod
    @abstractmethod
    def _metadata(
        llm: BaseChatModel,
        response: AIMessage | AIMessageChunk,
        elapsed_seconds: float,
    ) -> GenerationMetadata: ...

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
        logger.info(
            'Starting LLM generation: message_count=%d structured=%s tools=%d',
            len(messages),
            output_schema is not None,
            len(tools or []),
        )
        if output_schema is not None:
            runnable = self._llm.with_structured_output(
                output_schema, include_raw=True
            )
        elif tools:
            runnable = self._llm.bind_tools(tools)
        else:
            runnable = self._llm

        try:
            response = await runnable.ainvoke(
                self._to_langchain_messages(messages, system_prompt), **kwargs
            )
        except Exception as error:
            logger.error(
                'LLM generation failed: error_type=%s', type(error).__name__
            )
            raise
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

        result = GenerationResult(
            raw_text=str(raw_response.content),
            structured_output=structured_output,
            tool_calls=self._tool_calls(raw_response),
            usage=self._metadata(self._llm, raw_response, elapsed),
        )
        logger.info(
            'LLM generation completed: elapsed_seconds=%.3f output_tokens=%s',
            elapsed,
            result.usage.output_tokens,
        )
        return result

    async def stream(
        self,
        messages: list[MessageDTO],
        system_prompt: str,
        *,
        tools: list[ToolType] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[GenerationChunk | GenerationFinal]:
        logger.info(
            'Starting streamed LLM generation: message_count=%d tools=%d',
            len(messages),
            len(tools or []),
        )
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
        final = GenerationFinal(
            raw_text=''.join(text_parts),
            tool_calls=self._tool_calls(final_chunk),
            usage=self._metadata(self._llm, final_chunk, monotonic() - started),
        )
        logger.info(
            'Streamed LLM generation completed: elapsed_seconds=%.3f '
            'output_tokens=%s',
            final.usage.elapsed_seconds or 0,
            final.usage.output_tokens,
        )
        yield final
