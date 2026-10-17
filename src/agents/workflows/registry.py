from agents.workflows.base import WorkflowExecution


class WorkflowRegistry:
    def __init__(self) -> None:
        self._workflows: dict[str, type[WorkflowExecution]] = {}

    def registry(
        self, workflow_class: type[WorkflowExecution]
    ) -> type[WorkflowExecution]:
        if not issubclass(workflow_class, WorkflowExecution):
            raise TypeError(
                'Workflow class must inherit from WorkflowExecution'
            )

        for attribute in ('name', 'description', 'version'):
            value = getattr(workflow_class, attribute, None)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f'Workflow {attribute} must be a non-empty string'
                )

        existing = self._workflows.get(workflow_class.name)
        if existing is not None and existing is not workflow_class:
            raise ValueError(
                f'{workflow_class.name!r} workflow is already registered'
            )

        self._workflows[workflow_class.name] = workflow_class
        return workflow_class

    def get_workflow(self, name: str) -> WorkflowExecution:
        try:
            workflow_class = self._workflows[name]
        except KeyError as error:
            raise KeyError(f'Workflow {name!r} is not registered') from error
        return workflow_class()

    def list_workflows(self) -> list[type[WorkflowExecution]]:
        return list(self._workflows.values())


workflow_registry = WorkflowRegistry()
