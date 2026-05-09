def test_create_project_with_default_scenes(cli):
    r = cli.post("/api/projects", json={"name": "default", "desc": "d", "copy_default_scenes": True})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "default"
    assert data["scene_count"] == 1


def test_create_project_without_scenes(cli):
    r = cli.post("/api/projects", json={"name": "empty", "copy_default_scenes": False})
    assert r.status_code == 201
    assert r.json()["scene_count"] == 0


def test_duplicate_project_returns_409(cli):
    cli.post("/api/projects", json={"name": "dup", "copy_default_scenes": False})
    r = cli.post("/api/projects", json={"name": "dup", "copy_default_scenes": False})
    assert r.status_code == 409


def test_list_and_delete(cli):
    cli.post("/api/projects", json={"name": "a", "copy_default_scenes": False})
    cli.post("/api/projects", json={"name": "b", "copy_default_scenes": False})
    assert len(cli.get("/api/projects").json()) == 2
    pid_a = cli.get("/api/projects").json()[0]["id"]
    assert cli.delete(f"/api/projects/{pid_a}").status_code == 204
    assert len(cli.get("/api/projects").json()) == 1
