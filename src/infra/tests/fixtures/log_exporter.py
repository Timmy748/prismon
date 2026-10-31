import pytest
from opentelemetry.sdk._logs.export import (
    LogRecordExporter,
    LogRecordExportResult,
)


class MemoryLogExporter(LogRecordExporter):
    def __init__(self):
        self.records = []

    def export(self, batch):
        self.records.extend(batch)
        return LogRecordExportResult.SUCCESS

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        return True


@pytest.fixture
def memory_log_exporter():
    return MemoryLogExporter()
