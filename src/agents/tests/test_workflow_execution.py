from unittest.mock import patch

import pytest

from agents.workflows.base import WorkflowExecution


def test_workflow_execution_builds_graph_lazily_and_caches_it(example_workflow):
    workflow = example_workflow()

    with patch.object(
        workflow, '_build_graph', wraps=workflow._build_graph
    ) as build_graph:
        first_graph = workflow.graph
        second_graph = workflow.graph

    build_graph.assert_called_once_with()
    assert first_graph is second_graph


def test_workflow_execution_cannot_be_instantiated_without_abstract_methods():
    class IncompleteWorkflow(WorkflowExecution):
        name = 'incomplete'
        description = 'Incomplete workflow'
        version = '1'

    with pytest.raises(TypeError):
        IncompleteWorkflow()
