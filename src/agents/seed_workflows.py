import asyncio
from importlib import import_module
from pkgutil import iter_modules
from types import ModuleType

from sqlalchemy import select

import agents.workflows as workflows_package
from agents.database import get_session_factory
from agents.entities.workflow import Workflow
from agents.workflows.registry import WorkflowRegistry, workflow_registry


def _load_workflow_modules(package: ModuleType) -> None:  # pragma: no cover
    for module in iter_modules(package.__path__):
        if module.name not in {'base', 'registry'}:
            import_module(f'{workflows_package.__name__}.{module.name}')


async def seed_workflows(
    registry: WorkflowRegistry = workflow_registry,
) -> None:
    session_factory = get_session_factory()

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
    _load_workflow_modules(workflows_package)
    asyncio.run(seed_workflows())


if __name__ == '__main__':
    main()  # pragma: no cover
