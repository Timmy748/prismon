from typing import Any, AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_ollama import ChatOllama

from agents.dtos.message import MessageDTO
from agents.entities.message import SenderType
from agents.llm_engine.base import ILLMEngine, ToolType
from agents.settings import get_settings


class OllamaEngine(ILLMEngine):
    def __init__(self, llm: Any | None = None) -> None:
        if llm is None:
            settings = get_settings()
            llm = ChatOllama(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_MODEL,
                temperature=settings.OLLAMA_TEMPERATURE,
            )
        self._llm = llm

    def bind_tools(self, tools: list[ToolType]) -> 'OllamaEngine':
        langchain_tools = [convert_to_openai_tool(tool) for tool in tools]
        return OllamaEngine(llm=self._llm.bind_tools(langchain_tools))

    @staticmethod
    def _messages(
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

    async def generate(
        self, messages: list[MessageDTO], system_prompt: str, **kwargs: Any
    ) -> str:
        response = await self._llm.ainvoke(
            self._messages(messages, system_prompt), **kwargs
        )
        return str(response.content)

    async def stream(
        self, messages: list[MessageDTO], system_prompt: str, **kwargs: Any
    ) -> AsyncIterator[str]:
        async for chunk in self._llm.astream(
            self._messages(messages, system_prompt), **kwargs
        ):
            if chunk.content:
                yield str(chunk.content)

    async def generate_strutured[T](
        self,
        schema: type[T],
        messages: list[MessageDTO],
        system_prompt: str,
        **kwargs: Any,
    ) -> T:
        structured_llm = self._llm.with_structured_output(schema)
        return await structured_llm.ainvoke(
            self._messages(messages, system_prompt), **kwargs
        )
