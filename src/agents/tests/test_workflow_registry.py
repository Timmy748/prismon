import pytest

from agents.workflows.registry import WorkflowRegistry


def test_registry_registers_workflow_with_decorator(example_workflow):
    registry = WorkflowRegistry()

    @registry.registry
    class RegisteredWorkflow(example_workflow):
        pass

    assert registry.list_workflows() == [RegisteredWorkflow]


def test_registry_get_workflow_returns_an_instance(example_workflow):
    registry = WorkflowRegistry()
    registry.registry(example_workflow)

    workflow = registry.get_workflow('example')

    assert isinstance(workflow, example_workflow)


def test_registry_get_workflow_raises_for_unknown_name():
    registry = WorkflowRegistry()

    with pytest.raises(KeyError, match="Workflow 'missing' is not registered"):
        registry.get_workflow('missing')


def test_registry_rejects_class_that_does_not_inherit_workflow_execution():
    registry = WorkflowRegistry()

    with pytest.raises(TypeError, match='must inherit from WorkflowExecution'):
        registry.registry(object)


def test_registry_rejects_workflow_with_blank_metadata(example_workflow):
    class InvalidWorkflow(example_workflow):
        name = ' '

    registry = WorkflowRegistry()

    with pytest.raises(
        ValueError, match='Workflow name must be a non-empty string'
    ):
        registry.registry(InvalidWorkflow)


def test_registry_rejects_duplicate_workflow_name(example_workflow):
    class DuplicateWorkflow(example_workflow):
        description = 'A different workflow with the same name'

    registry = WorkflowRegistry()
    registry.registry(example_workflow)

    with pytest.raises(
        ValueError, match="'example' workflow is already registered"
    ):
        registry.registry(DuplicateWorkflow)
