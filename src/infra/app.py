from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from agents.routes.chats import router as chats_router
from agents.routes.workflows import router as workflows_router
from identity.routes.auth import router as auth_router
from identity.routes.user import router as user_router
from infra.logs import get_logger, setup_log
from project.routes.api_keys import router as api_keys_router
from project.routes.assets import router as assets_router
from project.routes.documents import router as documents_router
from project.routes.members import router as members_router
from project.routes.projects import router as projects_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_log()
    yield


app = FastAPI(title='Prismon API', lifespan=lifespan)


@app.exception_handler(Exception)
async def handle_unhandled_exception(
    request: Request, error: Exception
) -> PlainTextResponse:
    logger.error(
        'Unhandled API exception: method=%s path=%s',
        request.method,
        request.url.path,
        exc_info=(type(error), error, error.__traceback__),
    )
    return PlainTextResponse(
        'Internal Server Error', status_code=HTTPStatus.INTERNAL_SERVER_ERROR
    )


for router in (
    chats_router,
    workflows_router,
    user_router,
    projects_router,
    members_router,
    api_keys_router,
    documents_router,
    assets_router,
    auth_router,
):
    app.include_router(router)
