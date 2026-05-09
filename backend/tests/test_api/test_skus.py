import io


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
