import atexit
import logging
from threading import Event, Lock

from opentelemetry import _logs
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
    OTLPLogExporter,
)
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

from infra.settings import get_settings

_setup_lock = Lock()
_configured = Event()


def setup_log() -> None:
    with _setup_lock:
        if _configured.is_set():
            return

        settings = get_settings()
        provider = LoggerProvider(
            resource=Resource.create(
                {'service.name': settings.OTEL_SERVICE_NAME}
            )
        )
        exporter = OTLPLogExporter(
            endpoint=(
                settings.OTEL_EXPORTER_OTLP_LOGS_ENDPOINT
                or settings.OTEL_EXPORTER_OTLP_ENDPOINT
            )
        )
        provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
        _logs.set_logger_provider(provider)
        atexit.register(provider.shutdown)

        LoggingInstrumentor().instrument(
            inject_trace_context=True,
            enable_log_auto_instrumentation=False,
        )
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(
            LoggingHandler(level=logging.INFO, logger_provider=provider)
        )
        _configured.set()


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name)
