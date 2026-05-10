def test_scene_crud(cli):
    pid = cli.post("/api/projects", json={"name": "p", "copy_default_scenes": True}).json()["id"]

    # list 应该有 16 个内置场景
    scenes = cli.get(f"/api/projects/{pid}/scenes").json()
    assert len(scenes) == 17
    assert "大理石台·暖光" in [s["name"] for s in scenes]

    # create
    r = cli.post(f"/api/projects/{pid}/scenes", json={
        "name": "测试场景", "category": "测试", "prompt": "test prompt"
    })
    assert r.status_code == 201
    sid = r.json()["id"]

    # update
    r = cli.put(f"/api/projects/{pid}/scenes/{sid}", json={
        "name": "改名后", "category": "测试", "prompt": "new prompt"
    })
    assert r.status_code == 200
    assert r.json()["name"] == "改名后"

    # delete
    assert cli.delete(f"/api/projects/{pid}/scenes/{sid}").status_code == 204
