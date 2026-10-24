from fastapi import FastAPI

from agents.clients.identity import (
    create_identity_client as create_agents_identity_client,
)
from agents.clients.project import (
    create_project_client as create_agents_project_client,
)
from agents.routes.chats import create_chat_routes
from agents.routes.workflows import create_workflow_routes
from agents.unit_of_work import create_agents_unit_of_work
from core.logs import setup_log
from identity.routes.auth import create_auth_router
from identity.routes.user import create_user_router
from identity.security.jwt import create_token_provider
from identity.security.password_hasher import create_password_hasher
from identity.unit_of_work import create_identity_unit_of_work
from project.clients.client_user import create_identity_client
from project.routes.assets import create_assets_router
from project.routes.documents import create_documents_router
from project.routes.members import create_project_members_router
from project.routes.projects import create_project_router
from project.storage import create_storage
from project.unit_of_work import create_project_unit_of_work

setup_log()

app = FastAPI(title='Prismon API')
app.include_router(
    create_chat_routes(
        create_agents_unit_of_work,
        create_agents_identity_client,
        create_agents_project_client,
    )
)
app.include_router(create_workflow_routes(create_agents_unit_of_work))
app.include_router(
    create_user_router(
        create_password_hasher,
        create_token_provider,
        create_identity_unit_of_work,
    )
)
app.include_router(
    create_project_router(
        create_project_unit_of_work,
        create_identity_client,
    )
)
app.include_router(
    create_project_members_router(
        create_project_unit_of_work,
        create_identity_client,
    )
)
app.include_router(
    create_documents_router(
        create_project_unit_of_work,
        create_storage,
        create_identity_client,
    )
)
app.include_router(
    create_assets_router(
        create_project_unit_of_work,
        create_storage,
        create_identity_client,
    )
)
app.include_router(
    create_auth_router(
        create_password_hasher,
        create_token_provider,
        create_identity_unit_of_work,
    )
)
