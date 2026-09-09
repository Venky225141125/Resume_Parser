from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import clear_settings_cache
from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    clear_settings_cache()
    with TestClient(create_app()) as test_client:
        yield test_client
    clear_settings_cache()
