from img2ec.seeds.default_scenes import DEFAULT_SCENES


def test_default_scenes_count_is_16():
    assert len(DEFAULT_SCENES) == 16


def test_marble_scene_present():
    names = [s.name for s in DEFAULT_SCENES]
    assert "大理石台·暖光" in names


def test_categories_are_grouped():
    cats = {s.category for s in DEFAULT_SCENES}
    expected = {
        "通用·主图", "3C 数码", "3C/工具", "美妆/食品", "美妆/家居",
        "食品/家居", "户外/运动", "服饰/夏季", "服饰/书", "服饰",
        "节日·大促", "节日·春节", "节日·情人节", "母婴",
    }
    assert cats == expected


def test_all_scenes_have_required_fields():
    for s in DEFAULT_SCENES:
        assert s.name and s.category and s.prompt
        assert 0 <= s.ip_adapter_weight <= 100
        assert s.base_model == "flux-dev-fp8"
