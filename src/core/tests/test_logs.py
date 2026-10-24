import logging
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

from core import logs


def test_get_logger_returns_named_builtin_logger():
    logger = logs.get_logger('core.tests')

    assert logger is logging.getLogger('core.tests')


def test_get_logger_returns_root_logger_when_name_is_omitted():
    logger = logs.get_logger()

    assert logger is logging.getLogger()


def test_setup_log_exports_each_record_once_and_is_idempotent(
    monkeypatch,
    memory_log_exporter,
):
    root_logger = logging.getLogger()
    initial_handlers = list(root_logger.handlers)
    initial_level = root_logger.level
    settings = SimpleNamespace(
        OTEL_SERVICE_NAME='core-test-service',
        OTEL_EXPORTER_OTLP_LOGS_ENDPOINT='http://collector:4317',
        OTEL_EXPORTER_OTLP_ENDPOINT='http://fallback:4317',
    )
    exporter_factory = Mock(return_value=memory_log_exporter)
    instrument = Mock()

    monkeypatch.setattr(logs, '_configured', Event())
    monkeypatch.setattr(logs, 'get_settings', lambda: settings)
    monkeypatch.setattr(logs, 'OTLPLogExporter', exporter_factory)
    monkeypatch.setattr(logs.atexit, 'register', Mock())
    monkeypatch.setattr(
        logs.LoggingInstrumentor,
        'instrument',
        instrument,
    )

    try:
        logs.setup_log()
        logs.setup_log()

        logs.get_logger('core.tests.export').info('one exported record')
        provider = logs._logs.get_logger_provider()
        assert provider.force_flush()

        assert exporter_factory.call_count == 1
        assert exporter_factory.call_args.kwargs['endpoint'] == (
            'http://collector:4317'
        )
        instrument.assert_called_once_with(
            inject_trace_context=True,
            enable_log_auto_instrumentation=False,
        )
        assert len(root_logger.handlers) == len(initial_handlers) + 1
        assert len(memory_log_exporter.records) == 1
        exported_record = memory_log_exporter.records[0]
        assert exported_record.log_record.body == 'one exported record'
        assert exported_record.resource.attributes['service.name'] == (
            'core-test-service'
        )
    finally:
        for handler in list(root_logger.handlers):
            if handler not in initial_handlers:
                root_logger.removeHandler(handler)
                handler.close()
        root_logger.setLevel(initial_level)
