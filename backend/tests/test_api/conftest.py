import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from img2ec.db import get_session
from img2ec.main import create_app
from img2ec.models import Base


@pytest.fixture
def app_with_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("IMG2EC_DB_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("IMG2EC_ROOT_PATH", str(tmp_path / "projects"))

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    app = create_app()

    def override_session():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override_session
    return app


@pytest.fixture
def cli(app_with_db):
    return TestClient(app_with_db)
