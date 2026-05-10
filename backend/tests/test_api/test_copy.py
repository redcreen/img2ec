import io
from unittest.mock import patch


def _setup_done_sku(cli, app_with_db):
    pid = cli.post("/api/projects", json={"name": "p", "copy_default_scenes": True}).json()["id"]
    sid = cli.get(f"/api/projects/{pid}/scenes").json()[0]["id"]
    sku_id = cli.post(f"/api/projects/{pid}/skus", json={"name": "x", "scene_id": sid}).json()["id"]
    cli.post(f"/api/projects/{pid}/skus/{sku_id}/images",
             files={"file": ("a.jpg", io.BytesIO(b"x"), "image/jpeg")})

    # 手动把 SKU 状态改 done + master path，通过 app 的 dependency override 获取正确的 session
    from img2ec.db import get_session
    from img2ec.models import SKU, SKUStatus, SourceImage, ImageStatus

    db_gen = app_with_db.dependency_overrides[get_session]()
    db = next(db_gen)
    try:
        sku = db.get(SKU, sku_id)
        sku.status = SKUStatus.DONE.value
        img = sku.images[0]
        img.status = ImageStatus.DONE.value
        img.master_paths = {"1x1": "/tmp/fake-master.jpg"}
        db.commit()
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass

    return pid, sid, sku_id


def test_list_copy_empty(cli, app_with_db):
    _, _, sku_id = _setup_done_sku(cli, app_with_db)
    assert cli.get(f"/api/skus/{sku_id}/copy").json() == []


@patch("img2ec.api.copy.generate_copy_for_sku")
def test_regenerate_creates_3_copies(mock_gen, cli, app_with_db):
    mock_gen.return_value = {
        "vlm": {"category": "x", "appearance": "y", "key_features": ["a","b","c"]},
        "douyin": {"title": "t", "subtitle": "s", "selling_points": ["1","2","3"],
                   "description_md": "d", "category_path": "c", "keywords": ["k1","k2","k3","k4","k5"]},
        "shipinhao": {"title": "t", "subtitle": "s", "selling_points": ["1","2","3"],
                      "description_md": "d", "category_path": "c", "keywords": ["k1","k2","k3","k4","k5"]},
        "xiaohongshu": {"post_title": "pt", "post_body": "pb", "selling_points": ["1","2","3"],
                        "hashtags": ["#a","#b","#c","#d","#e"]},
    }
    _, _, sku_id = _setup_done_sku(cli, app_with_db)
    r = cli.post(f"/api/skus/{sku_id}/copy/regenerate")
    assert r.status_code == 201
    copies = r.json()
    plats = {c["platform"] for c in copies}
    assert plats == {"douyin", "shipinhao", "xiaohongshu"}
