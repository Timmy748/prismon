from unittest.mock import Mock

import pytest


@pytest.fixture(autouse=True)
def stub_embedding_enqueue(monkeypatch):
    sender = Mock()
    monkeypatch.setattr('project.use_cases.documents.send_task', sender)
    monkeypatch.setattr('project.use_cases.assets.send_task', sender)
    monkeypatch.setattr('project.use_cases.upload_intents.send_task', sender)
    return sender
