import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from img2ec.models import Base, Project, SKU, Platform, PlatformOutputCopy


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_create_copy(session):
    p = Project(id=str(uuid.uuid4()), name="p", root_path="/tmp")
    sku = SKU(id=str(uuid.uuid4()), project_id=p.id, name="测试 SKU")
    copy = PlatformOutputCopy(
        id=str(uuid.uuid4()), sku_id=sku.id, platform=Platform.DOUYIN.value,
        title="蓝色布艺猫", subtitle="纯手工苏绣",
        selling_points=["手工刺绣", "高品质"], description_md="## 商品介绍\n...",
        category_path="家居/工艺品", keywords=["刺绣", "猫"], hashtags=[],
    )
    session.add_all([p, sku, copy]); session.commit()
    fetched = session.query(PlatformOutputCopy).first()
    assert fetched.title == "蓝色布艺猫"
    assert fetched.selling_points == ["手工刺绣", "高品质"]
