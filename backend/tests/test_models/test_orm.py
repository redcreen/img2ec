import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from img2ec.models import Base, Project, Scene, SKU, SourceImage, SKUStatus, ImageStatus


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_project_with_scene_and_sku(session):
    p = Project(id=str(uuid.uuid4()), name="default", desc="d", root_path="/tmp/p")
    sc = Scene(
        id=str(uuid.uuid4()), project_id=p.id, name="大理石台·暖光",
        category="美妆/食品", prompt="on white marble, warm light",
    )
    sku = SKU(id=str(uuid.uuid4()), project_id=p.id, scene_id=sc.id, name="测试 SKU")
    img = SourceImage(id=str(uuid.uuid4()), sku_id=sku.id, name="front.jpg", src_path="/tmp/p/front.jpg")
    session.add_all([p, sc, sku, img])
    session.commit()

    fetched = session.query(Project).first()
    assert fetched.name == "default"
    assert len(fetched.scenes) == 1
    assert len(fetched.skus) == 1
    assert fetched.skus[0].images[0].status == ImageStatus.PENDING.value


def test_cascade_delete(session):
    p = Project(id="p1", name="default", root_path="/tmp/p1")
    sku = SKU(id="s1", project_id="p1", name="测试")
    img = SourceImage(id="i1", sku_id="s1", name="a.jpg", src_path="/tmp/a.jpg")
    session.add_all([p, sku, img])
    session.commit()

    session.delete(p)
    session.commit()

    assert session.query(SKU).count() == 0
    assert session.query(SourceImage).count() == 0
