from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any, TypedDict

from langchain_core.runnables import Runnable
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from agents.dtos.message import CreateMessageDTO, MessageDTO
from agents.entities.message import SenderType
from agents.llm_engine.base import (
    GenerationChunk,
    GenerationFinal,
    ILLMEngine,
)
from agents.workflows.base import WorkflowExecution
from agents.workflows.registry import workflow_registry

CHAT_SYSTEM_PROMPT = (
    'Você é um assistente útil. Responda à mensagem do usuário.'
)


class ChatState(TypedDict):
    messages: list[MessageDTO]
    generation: GenerationFinal


ChatGenerationEvent = GenerationChunk | GenerationFinal


@workflow_registry.registry
class ChatWorkflow(WorkflowExecution):
    name = 'chat'
    description = 'Conversa simples usando o histórico do chat.'
    version = '1'

    def __init__(self, engine: ILLMEngine) -> None:
        super().__init__(engine=engine)

    async def stream(
        self, thread_id: str, input: dict[str, Any]
    ) -> AsyncIterator[ChatGenerationEvent]:
        messages: list[MessageDTO] = input['messages']
        async for event in self.graph.astream(
            {'messages': messages}, stream_mode='custom'
        ):
            yield event

    async def run(
        self, thread_id: str, input: dict[str, Any]
    ) -> CreateMessageDTO:
        final: GenerationFinal | None = None
        async for event in self.stream(thread_id, input):
            if isinstance(event, GenerationFinal):
                final = event

        if final is None:
            raise RuntimeError(
                'Chat workflow finished without a final generation'
            )

        return self._to_message(final)

    async def resume(
        self, thread_id: str, input: dict[str, Any]
    ) -> CreateMessageDTO:
        return await self.run(thread_id, input)

    def _to_message(self, result: GenerationFinal) -> CreateMessageDTO:
        return CreateMessageDTO(
            parent_id=None,
            sender_type=SenderType.ASSISTANT,
            text=result.raw_text,
            payload={},
            meta_data={
                'workflow': self.name,
                'version': self.version,
                **asdict(result.usage),
            },
        )

    def _build_graph(self) -> Runnable[Any, Any]:
        async def respond(state: ChatState) -> dict[str, GenerationFinal]:
            writer = get_stream_writer()
            final: GenerationFinal | None = None

            async for event in self._engine.stream(
                state['messages'], CHAT_SYSTEM_PROMPT
            ):
                writer(event)
                if isinstance(event, GenerationFinal):
                    final = event

            if final is None:
                raise RuntimeError(
                    'LLM engine stream finished without a final generation'
                )
            return {'generation': final}

        builder = StateGraph(ChatState)
        builder.add_node('respond', respond)
        builder.add_edge(START, 'respond')
        builder.add_edge('respond', END)
        return builder.compile()
