import asyncio

from sqlalchemy import select

from agents.database import get_session_factory
from agents.entities.workflow import Workflow
from agents.workflows.registry import (
    WorkflowRegistry,
    workflow_registry_factory,
)


async def seed_workflows(registry: WorkflowRegistry | None = None) -> None:
    session_factory = get_session_factory()
    if registry is None:
        registry = workflow_registry_factory()

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
                continue

            if (
                workflow.description != workflow_class.description
                or workflow.version != workflow_class.version
            ):
                workflow.description = workflow_class.description
                workflow.version = workflow_class.version

        await session.commit()


def main() -> None:  # pragma: no cover
    asyncio.run(seed_workflows())


if __name__ == '__main__':
    main()  # pragma: no cover
