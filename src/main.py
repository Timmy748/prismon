from fastapi import FastAPI

from identity.repositories.token import create_refresh_token_repository
from identity.repositories.user import create_user_repository
from identity.routes.auth import create_auth_router
from identity.routes.user import create_user_router
from identity.security.jwt import create_token_provider
from identity.security.password_hasher import create_password_hasher

app = FastAPI(title='Prismon API')
app.include_router(
    create_user_router(
        create_password_hasher, create_token_provider, create_user_repository
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
