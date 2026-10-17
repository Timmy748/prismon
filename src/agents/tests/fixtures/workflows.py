from collections.abc import Sequence
from typing import Any

import pytest
from langchain_core.runnables import Runnable, RunnableLambda

from agents.entities.workflow import Workflow
from agents.workflows.base import WorkflowExecution
from agents.workflows.registry import WorkflowRegistry


class ExampleWorkflow(WorkflowExecution):
    name = 'example'
    description = 'Example workflow'
    version = '1'

    async def run(self, thread_id: str, input: dict[str, Any]) -> Any:
        return input

    async def resume(self, thread_id: str, input: dict[str, Any]) -> Any:
        return input

    def _build_graph(self) -> Runnable[Any, Any]:
        return RunnableLambda(lambda value: value)


class FakeWorkflowScalars:
    def __init__(self, workflows: Sequence[Workflow]) -> None:
        self._workflows = workflows

    def all(self) -> Sequence[Workflow]:
        return self._workflows


class FakeWorkflowSession:
    def __init__(self, workflows: Sequence[Workflow]) -> None:
        self.workflows = list(workflows)
        self.added: list[Workflow] = []
        self.commit_count = 0

    async def __aenter__(self) -> 'FakeWorkflowSession':
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def scalars(self, statement: object) -> FakeWorkflowScalars:
        return FakeWorkflowScalars(self.workflows)

    def add(self, workflow: Workflow) -> None:
        self.added.append(workflow)

    async def commit(self) -> None:
        self.commit_count += 1


class FakeWorkflowSessionFactory:
    def __init__(self, session: FakeWorkflowSession) -> None:
        self.session = session

    def __call__(self) -> FakeWorkflowSession:
        return self.session


@pytest.fixture
def example_workflow():
    return ExampleWorkflow


@pytest.fixture
def example_workflow_registry(example_workflow):
    registry = WorkflowRegistry()
    registry.registry(example_workflow)
    return registry


@pytest.fixture
def workflow_session_builder():
    def build(workflows: Sequence[Workflow] = ()) -> FakeWorkflowSession:
        return FakeWorkflowSession(workflows)

    return build


@pytest.fixture
def workflow_session_factory_builder():
    def build(session: FakeWorkflowSession) -> FakeWorkflowSessionFactory:
        return FakeWorkflowSessionFactory(session)

    return build
