from unittest.mock import patch

import pytest

import agents.seed_workflows as seed_module


@pytest.mark.asyncio
async def test_seed_workflows_uses_default_registry(
    example_workflow,
    example_workflow_registry,
    workflow_session_builder,
    workflow_session_factory_builder,
):
    session = workflow_session_builder()
    session_factory = workflow_session_factory_builder(session)

    with (
        patch.object(
            seed_module,
            'get_session_factory',
            return_value=session_factory,
        ),
        patch.object(
            seed_module,
            'workflow_registry_factory',
            return_value=example_workflow_registry,
        ) as registry_factory,
    ):
        await seed_module.seed_workflows()

    registry_factory.assert_called_once_with()
    assert len(session.added) == 1
    assert session.added[0].name == example_workflow.name
    assert session.commit_count == 1
