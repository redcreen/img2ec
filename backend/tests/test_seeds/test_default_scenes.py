from img2ec.seeds.default_scenes import DEFAULT_SCENES


def test_mvp_has_exactly_one_scene():
    assert len(DEFAULT_SCENES) == 1


def test_mvp_scene_has_required_fields():
    scene = DEFAULT_SCENES[0]
    assert scene.name == "大理石台·暖光"
    assert scene.category == "美妆/食品"
    assert "marble" in scene.prompt.lower()
    assert scene.base_model == "flux-dev-fp8"
    assert 0 <= scene.ip_adapter_weight <= 100
