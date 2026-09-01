from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql://app:app@127.0.0.1:55434/inkworks")
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ["DEMO_EXPOSE_TOKENS"] = "true"
os.environ["DELAY_MAX_MS"] = "10"
os.environ.pop("OPENAI_API_KEY", None)

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
