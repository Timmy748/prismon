from fastapi import FastAPI

from identity.repositories.token import create_refresh_token_repository
from identity.repositories.user import create_user_repository
from identity.routes.auth import create_auth_router
from identity.routes.user import create_user_router
from identity.security.jwt import create_token_provider
from identity.security.password_hasher import create_password_hasher
from project.clients.client_user import create_identity_client
from project.repositories.asset import create_asset_repository
from project.repositories.document import create_document_repository
from project.repositories.member import create_member_repository
from project.repositories.project import create_project_repository
from project.routes.assets import create_assets_router
from project.routes.documents import create_documents_router
from project.routes.members import create_project_members_router
from project.routes.projects import create_project_router
from project.storage import create_storage

app = FastAPI(title='Prismon API')
app.include_router(
    create_user_router(
        create_password_hasher, create_token_provider, create_user_repository
    )
)
app.include_router(
    create_project_router(
        create_project_repository,
        create_member_repository,
        create_identity_client,
    )
)
app.include_router(
    create_project_members_router(
        create_project_repository,
        create_member_repository,
        create_identity_client,
    )
)
app.include_router(
    create_documents_router(
        create_project_repository,
        create_member_repository,
        create_document_repository,
        create_storage,
        create_identity_client,
    )
)
app.include_router(
    create_assets_router(
        create_project_repository,
        create_member_repository,
        create_asset_repository,
        create_storage,
        create_identity_client,
    )
)
app.include_router(
    create_auth_router(
        create_password_hasher,
        create_token_provider,
        create_user_repository,
        create_refresh_token_repository,
    )
)
