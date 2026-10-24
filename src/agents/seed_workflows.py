import asyncio

from sqlalchemy import select

from agents.database import get_session_factory
from agents.entities.workflow import Workflow
from agents.workflows.registry import (
    WorkflowRegistry,
    workflow_registry_factory,
)
from core.logs import get_logger, setup_log

logger = get_logger(__name__)


async def seed_workflows(registry: WorkflowRegistry | None = None) -> None:
    logger.info('Starting workflow seed')
    session_factory = get_session_factory()
    if registry is None:
        registry = workflow_registry_factory()

    created_count = 0
    updated_count = 0
    unchanged_count = 0
    async with session_factory() as session:
        existing_workflows = {
            workflow.name: workflow
            for workflow in (await session.scalars(select(Workflow))).all()
        }

        for workflow_class in registry.list_workflows():
            workflow = existing_workflows.get(workflow_class.name)
            if workflow is None:
                session.add(
                    Workflow(
                        name=workflow_class.name,
                        description=workflow_class.description,
                        version=workflow_class.version,
                    )
                )
                created_count += 1
                logger.info(
                    'Created workflow during seed: %s', workflow_class.name
                )
                continue

            if (
                workflow.description != workflow_class.description
                or workflow.version != workflow_class.version
            ):
                workflow.description = workflow_class.description
                workflow.version = workflow_class.version
                updated_count += 1
                logger.info(
                    'Updated workflow metadata during seed: %s',
                    workflow_class.name,
                )
            else:
                unchanged_count += 1

        await session.commit()
        logger.info(
            'Workflow seed completed: created=%d updated=%d unchanged=%d',
            created_count,
            updated_count,
            unchanged_count,
        )


def main() -> None:  # pragma: no cover
    setup_log()
    try:
        asyncio.run(seed_workflows())
    except Exception:
        logger.exception('Workflow seed failed')
        raise


if __name__ == '__main__':
    main()  # pragma: no cover
