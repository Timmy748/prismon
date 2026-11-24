from unittest.mock import patch

import pytest

import agents.seed_workflows as seed_module
from agents.entities.workflow import Workflow


@pytest.mark.asyncio
async def test_seed_workflows_creates_missing_workflow(
    example_workflow,
    example_workflow_registry,
    workflow_session_builder,
    workflow_session_factory_builder,
):
    session = workflow_session_builder()
    session_factory = workflow_session_factory_builder(session)

    with patch.object(
        seed_module, 'get_session_factory', return_value=session_factory
    ):
        await seed_module.seed_workflows(example_workflow_registry)

    assert len(session.added) == 1
    assert session.added[0].name == example_workflow.name
    assert session.added[0].description == example_workflow.description
    assert session.added[0].version == example_workflow.version
    assert session.added[0].config == example_workflow.config
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_seed_workflows_updates_changed_metadata(
    example_workflow,
    example_workflow_registry,
    workflow_session_builder,
    workflow_session_factory_builder,
):
    existing = Workflow(
        name=example_workflow.name,
        description='Old description',
        version='0',
    )
    session = workflow_session_builder([existing])
    session_factory = workflow_session_factory_builder(session)

    with patch.object(
        seed_module, 'get_session_factory', return_value=session_factory
    ):
        await seed_module.seed_workflows(example_workflow_registry)

    assert session.added == []
    assert existing.description == example_workflow.description
    assert existing.version == example_workflow.version
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_seed_workflows_updates_changed_config(
    example_workflow,
    example_workflow_registry,
    workflow_session_builder,
    workflow_session_factory_builder,
    monkeypatch,
):
    old_config = {'retrieve': {'fields': ['old']}}
    new_config = {'retrieve': {'fields': ['question']}}
    monkeypatch.setattr(example_workflow, 'config', new_config)
    existing = Workflow(
        name=example_workflow.name,
        description=example_workflow.description,
        version=example_workflow.version,
    )
    existing.config = old_config
    session = workflow_session_builder([existing])
    session_factory = workflow_session_factory_builder(session)

    with patch.object(
        seed_module, 'get_session_factory', return_value=session_factory
    ):
        await seed_module.seed_workflows(example_workflow_registry)

    assert existing.config == new_config
    assert session.added == []


@pytest.mark.asyncio
async def test_seed_workflows_leaves_unchanged_metadata_as_is(
    example_workflow,
    example_workflow_registry,
    workflow_session_builder,
    workflow_session_factory_builder,
):
    existing = Workflow(
        name=example_workflow.name,
        description=example_workflow.description,
        version=example_workflow.version,
    )
    existing.config = example_workflow.config
    original_config_entity = existing.workflow_config
    session = workflow_session_builder([existing])
    session_factory = workflow_session_factory_builder(session)

    with patch.object(
        seed_module, 'get_session_factory', return_value=session_factory
    ):
        await seed_module.seed_workflows(example_workflow_registry)

    assert session.added == []
    assert existing.description == example_workflow.description
    assert existing.version == example_workflow.version
    assert existing.workflow_config is original_config_entity
    assert session.commit_count == 1
