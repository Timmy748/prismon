from collections.abc import Mapping

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_openrouter import ChatOpenRouter

from agents.llm_engine.base import GenerationMetadata
from agents.llm_engine.langchain_base import LangChainEngine
from infra.logs import get_logger
from infra.settings import get_settings

logger = get_logger(__name__)


class OpenRouterEngine(LangChainEngine):
    def __init__(
        self,
        api_key: str,
        llm: BaseChatModel | None = None,
    ) -> None:
        super().__init__(api_key, llm)

    @staticmethod
    def _create_llm(api_key: str) -> BaseChatModel:
        settings = get_settings()
        if not api_key.strip():
            raise ValueError('API key must be provided for OpenRouter')
        if not settings.OPENROUTER_MODEL.strip():
            raise ValueError('OPENROUTER_MODEL must be configured')
        logger.info(
            'Configuring OpenRouter chat engine: model=%s',
            settings.OPENROUTER_MODEL,
        )
        return ChatOpenRouter(
            api_key=api_key,
            model=settings.OPENROUTER_MODEL,
            temperature=settings.OPENROUTER_TEMPERATURE,
            stream_usage=True,
        )

    @staticmethod
    def _metadata(
        llm: BaseChatModel,
        response: AIMessage | AIMessageChunk,
        elapsed_seconds: float,
    ) -> GenerationMetadata:
        response_metadata = response.response_metadata
        usage = response.usage_metadata or {}
        provider_usage = response_metadata.get('token_usage') or {}
        if not isinstance(provider_usage, Mapping):
            provider_usage = {}

        input_tokens = usage.get('input_tokens')
        if input_tokens is None:
            input_tokens = provider_usage.get('prompt_tokens')
        output_tokens = usage.get('output_tokens')
        if output_tokens is None:
            output_tokens = provider_usage.get('completion_tokens')
        total_tokens = usage.get('total_tokens')
        if total_tokens is None:
            total_tokens = provider_usage.get('total_tokens')
        if (
            total_tokens is None
            and isinstance(input_tokens, (int, float))
            and isinstance(output_tokens, (int, float))
        ):
            total_tokens = input_tokens + output_tokens

        tokens_per_second = None
        if (
            isinstance(output_tokens, (int, float))
            and output_tokens > 0
            and elapsed_seconds > 0
        ):
            tokens_per_second = output_tokens / elapsed_seconds

        model = (
            response_metadata.get('model_name')
            or response_metadata.get('model')
            or getattr(llm, 'model_name', None)
            or getattr(llm, 'model', None)
        )
        finish_reason = response_metadata.get(
            'finish_reason'
        ) or response_metadata.get('stop_reason')
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
