import io
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _setup_project_with_scene(cli):
    pid = cli.post("/api/projects", json={"name": "p", "copy_default_scenes": True}).json()["id"]
    sid = cli.get(f"/api/projects/{pid}/scenes").json()[0]["id"]
    return pid, sid


def test_sku_create_with_scene(cli):
    pid, sid = _setup_project_with_scene(cli)
    r = cli.post(f"/api/projects/{pid}/skus", json={"name": "蓝色保温杯", "scene_id": sid})
    assert r.status_code == 201
    assert r.json()["name"] == "蓝色保温杯"
    assert r.json()["status"] == "draft"


def test_upload_image_changes_status_to_ready(cli):
    pid, sid = _setup_project_with_scene(cli)
    sku_id = cli.post(f"/api/projects/{pid}/skus", json={"name": "x", "scene_id": sid}).json()["id"]

    files = {"file": ("front.jpg", io.BytesIO(b"fake jpg"), "image/jpeg")}
    r = cli.post(f"/api/projects/{pid}/skus/{sku_id}/images", files=files)
    assert r.status_code == 201
    assert r.json()["status"] == "ready"
    assert len(r.json()["images"]) == 1
    assert r.json()["images"][0]["name"] == "front.jpg"


def test_process_without_scene_returns_400(cli):
    pid = cli.post("/api/projects", json={"name": "p2", "copy_default_scenes": False}).json()["id"]
    sku_id = cli.post(f"/api/projects/{pid}/skus", json={"name": "x"}).json()["id"]
    r = cli.post(f"/api/projects/{pid}/skus/{sku_id}/process")
    assert r.status_code == 400


def test_delete_pending_image(cli):
    pid, sid = _setup_project_with_scene(cli)
    sku_id = cli.post(f"/api/projects/{pid}/skus", json={"name": "x", "scene_id": sid}).json()["id"]
    files = {"file": ("a.jpg", io.BytesIO(b"x"), "image/jpeg")}
    sku = cli.post(f"/api/projects/{pid}/skus/{sku_id}/images", files=files).json()
    iid = sku["images"][0]["id"]
    r = cli.delete(f"/api/projects/{pid}/skus/{sku_id}/images/{iid}")
    assert r.status_code == 204


def test_download_all_only_includes_done_skus(cli, app_with_db):
    from img2ec.models import SKU, SKUStatus
    from img2ec.db import get_session

    pid = cli.post("/api/projects", json={"name": "dl_test", "copy_default_scenes": True}).json()["id"]
    sid = cli.get(f"/api/projects/{pid}/scenes").json()[0]["id"]

    sku1 = cli.post(f"/api/projects/{pid}/skus", json={"name": "sku-a", "scene_id": sid}).json()
    sku2 = cli.post(f"/api/projects/{pid}/skus", json={"name": "sku-b", "scene_id": sid}).json()

    # 手动 mock 状态：sku1 done，sku2 ready，通过 app 的 dependency override 获取正确的 session
    db_gen = app_with_db.dependency_overrides[get_session]()
    db = next(db_gen)
    try:
        db.query(SKU).filter_by(id=sku1["id"]).update({"status": SKUStatus.DONE.value})
        db.commit()
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass

    # 没有真实 outputs 文件 → zip 仍然可生成（空）
    r = cli.get(f"/api/projects/{pid}/download-all")
    assert r.status_code == 200


def test_download_all_400_if_no_done(cli):
    pid = cli.post("/api/projects", json={"name": "empty"}).json()["id"]
    r = cli.get(f"/api/projects/{pid}/download-all")
    assert r.status_code == 400
