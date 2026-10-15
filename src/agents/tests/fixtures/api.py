import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def api_client():
    def create_client(router: APIRouter) -> TestClient:
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    return create_client
