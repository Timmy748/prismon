from project.unit_of_work import IProjectUnitOfWork


async def should_finalize_upload(
    uow: IProjectUnitOfWork, object_key: str
) -> bool:
    intent = await uow.upload_intent_repository.get_by_object_key(object_key)
    if intent is not None:
        return True

    event = await uow.resource_event_repository.get_by_idempotency_key(
        object_key
    )
    return event is not None and event.event_type in {
        'file_changed',
        'upload_failed',
    }
