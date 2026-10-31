from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_ollama import ChatOllama

from agents.llm_engine.base import GenerationMetadata
from agents.llm_engine.langchain_base import LangChainEngine
from infra.logs import get_logger
from infra.settings import get_settings

logger = get_logger(__name__)


class OllamaEngine(LangChainEngine):
    def __init__(
        self,
        api_key: str,
        llm: BaseChatModel | None = None,
    ) -> None:
        super().__init__(api_key, llm)

    @staticmethod
    def _create_llm(api_key: str) -> BaseChatModel:
        del api_key
        settings = get_settings()
        logger.info(
            'Configuring Ollama chat engine: model=%s', settings.OLLAMA_MODEL
        )
        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            temperature=settings.OLLAMA_TEMPERATURE,
        )

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
