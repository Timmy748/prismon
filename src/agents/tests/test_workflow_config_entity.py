from agents.entities.workflow import Workflow, WorkflowConfig


def test_workflow_without_config_returns_empty_dict():
    workflow = Workflow(
        name='chat', description='Chat workflow', version='1.0.0'
    )

    assert workflow.config == {}


def test_workflow_config_setter_creates_and_updates_one_related_entity():
    workflow = Workflow(
        name='chat', description='Chat workflow', version='1.0.0'
    )
    initial_config = {'retrieve': {'fields': ['question']}}

    workflow.config = initial_config
    related_config = workflow.workflow_config
    workflow.config = {'respond': {'fields': ['temperature']}}

    assert isinstance(related_config, WorkflowConfig)
    assert workflow.workflow_config is related_config
    assert workflow.config == {'respond': {'fields': ['temperature']}}
